"""
Amazon FR Fetcher — Redis Worker
Request format:  {"url": "...", "proxy_type": "standard|none", "ret_key": "..."}
Response format: {"status", "html", "headers", "http_code", "cookies", "elapsed_ms",
                  "ret_key", "url", "proxy_type", "country", "total_elapsed_seconds", "log", "error"}
"""

import time
from typing import Dict, Any

from config import load_proxies_from_excel, MAX_RETRIES
from extractor import AmazonFetcher
from utils import load_cookie_string, AMAZON_COUNTRY


async def process_single_request(request: Dict[str, Any]) -> Dict[str, Any]:
    url = request.get('url')
    ret_key = request.get('ret_key', 'unknown')
    proxy_type = request.get('proxy_type', 'standard')

    if not url:
        return {
            'ret_key': ret_key,
            'url': None,
            'error': 'Missing url',
            'status': 'failed',
        }

    proxies = []
    if proxy_type == 'standard':
        proxies = load_proxies_from_excel()

    fetcher = AmazonFetcher(proxy_list=proxies, cookie_string=load_cookie_string())
    start_time = time.time()
    try:
        result_obj = await fetcher.fetch_url(url, max_retries=MAX_RETRIES)
        elapsed = time.time() - start_time

        result_dict = result_obj.to_dict()
        result_dict['ret_key'] = ret_key
        result_dict['proxy_type'] = proxy_type
        result_dict['country'] = AMAZON_COUNTRY
        result_dict['total_elapsed_seconds'] = elapsed
        result_dict['log'] = fetcher.log_buffer
        return result_dict

    except Exception as e:
        return {
            'ret_key': ret_key,
            'url': url,
            'proxy_type': proxy_type,
            'html': '',
            'headers': {},
            'http_code': None,
            'cookies': {},
            'elapsed_ms': 0,
            'country': AMAZON_COUNTRY,
            'error': str(e),
            'status': 'failed',
            'total_elapsed_seconds': time.time() - start_time,
            'log': fetcher.log_buffer,
        }
    finally:
        await fetcher.close_browser()
