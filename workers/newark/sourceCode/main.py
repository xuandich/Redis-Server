import asyncio
import json
import argparse
import time
from typing import List, Dict, Any
from asyncio import Semaphore

from extractor import NewarkProductExtractor
from utils import load_proxies_from_excel, normalize_urls, read_keys_from_excel


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


async def worker_task(proxy_list: List[str], urls: List[str]) -> Dict:
    print(f"\n{'='*60}")
    print(f"🏭 Khởi động với {len(urls)} URLs và {len(proxy_list)} proxies")
    print(f"{'='*60}")

    extractor = NewarkProductExtractor(proxy_list)

    try:
        results = await extractor.process_urls(urls)
        return {'results': results}

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return {'results': []}

    finally:
        await extractor.close_browser()


async def main():
    parser = argparse.ArgumentParser(
        description="Newark Product Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --urls key1 key2 key3
  python main.py --urls "https://www.newark.com/dp/key1" "https://www.newark.com/dp/key2"
  python main.py --urls-file input/url.xlsx
  python main.py  (uses default input/url.xlsx)
        """
    )

    parser.add_argument('--urls', nargs='+', help='URLs hoặc keys trực tiếp (space-separated)')
    parser.add_argument('--urls-file', default='input/url.xlsx', help='File Excel chứa URLs')
    parser.add_argument('--proxies-file', default='Proxy/buyproxies_List.xlsx', help='File Excel chứa proxy list')
    args = parser.parse_args()

    print("\n" + "="*60)
    print("     🎯 NEWARK URL FETCHER")
    print("     Trả về HTML, headers, cookies, http_code")
    print("="*60)

    proxies = load_proxies_from_excel(args.proxies_file)

    if not proxies:
        print("\n⚠️ Không tìm thấy proxy! Tiếp tục không proxy...")
        proxies = []

    if args.urls:
        all_keys = normalize_urls(args.urls)
    else:
        all_keys = read_keys_from_excel(args.urls_file)

    if not all_keys:
        print("\n❌ Không có key nào!")
        return

    TOTAL_TIMEOUT = 300  # 5 phút

    try:
        worker_result = await asyncio.wait_for(worker_task(proxies, all_keys), timeout=TOTAL_TIMEOUT)
        all_results = worker_result.get('results', [])
    except asyncio.TimeoutError:
        print(f"\n⏰ Timeout sau {TOTAL_TIMEOUT}s — dừng toàn bộ quá trình")
        all_results = [{'html': None, 'headers': {}, 'http_code': 0, 'cookies': [], 'elapsed_ms': TOTAL_TIMEOUT * 1000, 'error': 'Total timeout exceeded', 'log': []}]

    # TODO: push all_results to Redis
    print(json.dumps(all_results, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
