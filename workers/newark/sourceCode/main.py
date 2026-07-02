import time
from typing import Dict, Any
from asyncio import Semaphore

from extractor import NewarkProductExtractor
from utils import load_proxies_from_excel


async def process_single_request(request: Dict[str, Any], semaphore: Semaphore) -> Dict[str, Any]:
    """Entry point cho Redis worker — xử lý một request đơn lẻ"""
    async with semaphore:
        url = request.get('url')
        ret_key = request.get('ret_key', 'unknown')
        proxy_type = request.get('proxy_type', 'standard')

        if not url:
            return {'ret_key': ret_key, 'url': None, 'error': 'Missing url', 'status': 'failed'}

        proxies = []
        if proxy_type == 'standard':
            proxies = load_proxies_from_excel('Proxy/buyproxies_List.xlsx')

        extractor = NewarkProductExtractor(proxies)
        start_time = time.time()
        try:
            results = await extractor.process_urls([url])
            elapsed = time.time() - start_time
            if not results:
                return {
                    'ret_key': ret_key, 'url': url, 'proxy_type': proxy_type,
                    'html': '', 'headers': {}, 'http_code': None, 'cookies': {},
                    'elapsed_ms': 0, 'error': 'No result from extractor',
                    'status': 'failed', 'total_elapsed_seconds': elapsed,
                }
            r = results[0]
            r['ret_key'] = ret_key
            r['url'] = url
            r['proxy_type'] = proxy_type
            r['total_elapsed_seconds'] = elapsed
            r['status'] = 'success' if r.get('html') else 'failed'
            return r
        except Exception as e:
            return {
                'ret_key': ret_key, 'url': url, 'proxy_type': proxy_type,
                'html': '', 'headers': {}, 'http_code': None, 'cookies': {},
                'elapsed_ms': 0, 'error': str(e),
                'status': 'failed', 'total_elapsed_seconds': time.time() - start_time,
            }
        finally:
            await extractor.close_browser()
