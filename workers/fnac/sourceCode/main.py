#!/usr/bin/env python3
"""
FNAC HTML Fetcher - Xử lý mảng request
Request format: {"url": "...", "mode": "none", "proxy_type": "standard", "ret_key": "..."}
Response format: như request + thêm html, headers, http_code, cookies, elapsed_ms, error, status, ...
"""

import asyncio
import time
from typing import List, Dict, Any
from asyncio import Semaphore

from config import ensure_directories, load_proxies_from_excel
from extractor import FnacHtmlFetcher


async def process_single_request(request: Dict[str, Any], semaphore: Semaphore) -> Dict[str, Any]:
    """Xử lý một request đơn lẻ với semaphore giới hạn đồng thời"""
    async with semaphore:
        url = request.get('url')
        ret_key = request.get('ret_key', 'unknown')
        proxy_type = request.get('proxy_type', 'standard')
        # mode = request.get('mode', 'none')  # dự phòng

        if not url:
            return {
                'ret_key': ret_key,
                'url': None,
                'error': 'Missing url',
                'status': 'failed'
            }

        ensure_directories()

        proxies = []
        if proxy_type == 'standard':
            proxies = load_proxies_from_excel()

        fetcher = FnacHtmlFetcher(
            proxy_list=proxies,
            worker_id=hash(ret_key) % 1000,
            semaphore=None,
            display_manager=None
        )

        start_time = time.time()
        try:
            results = await fetcher.process_keys_with_retry([url], max_retries=3)
            elapsed = time.time() - start_time
            if not results:
                return {
                    'ret_key': ret_key,
                    'url': url,
                    'error': 'No result',
                    'status': 'failed',
                    'total_elapsed_seconds': elapsed
                }
            result_dict = results[0].to_dict()
            result_dict['ret_key'] = ret_key
            result_dict['total_elapsed_seconds'] = elapsed
            result_dict['mode'] = request.get('mode', 'none')
            result_dict['proxy_type'] = proxy_type
            result_dict['log'] = fetcher.log_buffer
            return result_dict
        except Exception as e:
            return {
                'ret_key': ret_key,
                'url': url,
                'error': str(e),
                'status': 'failed',
                'total_elapsed_seconds': time.time() - start_time,
                'log': fetcher.log_buffer,
            }
        finally:
            await fetcher.close_browser()


async def process_request_list(requests: List[Dict[str, Any]], max_concurrent: int = 5) -> List[Dict[str, Any]]:
    """
    Xử lý một danh sách các request, chạy song song với giới hạn max_concurrent.
    Trả về danh sách kết quả theo đúng thứ tự đầu vào.
    """
    semaphore = Semaphore(max_concurrent)
    tasks = [process_single_request(req, semaphore) for req in requests]
    results = await asyncio.gather(*tasks)
    return results