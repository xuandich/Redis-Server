"""
Amazon Product Scraper — Batch processor
Request:  đọc danh sách URL từ Excel
Response: lưu kết quả ra CSV + JSON
"""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from config import load_proxies_from_excel, INPUT_FILE, OUTPUT_DIR, MAX_RETRIES, MAX_URLS
from extractor import AmazonFetcher
from utils import clean_amazon_url, load_cookie_string, AMAZON_COUNTRY


def read_urls(input_file: str) -> List[str]:
    if not Path(input_file).exists():
        print(f"❌ Không tìm thấy: {input_file}")
        return []
    df = pd.read_excel(input_file, header=None)
    urls = [
        row[0] for _, row in df.iterrows()
        if isinstance(row[0], str) and row[0].startswith('http')
    ]
    urls = [clean_amazon_url(u) for u in urls]
    if MAX_URLS:
        urls = urls[:MAX_URLS]
    print(f"✅ Đã đọc {len(urls)} URLs")
    return urls


def save_results(results: List[Dict]):
    success = [r for r in results if r.get('status') == 'success']
    if not success:
        print("⚠️ Không có dữ liệu thành công")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    df = pd.DataFrame(success)
    df['scraped_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    csv_path = os.path.join(OUTPUT_DIR, f"amazon_products_{ts}.csv")
    json_path = os.path.join(OUTPUT_DIR, f"amazon_products_{ts}.json")
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df.to_json(json_path, orient='records', force_ascii=False, indent=2)

    print(f"✅ CSV:  {csv_path}")
    print(f"✅ JSON: {json_path}")
    print(f"📊 Tổng: {len(results)} | Thành công: {len(success)} | Thất bại: {len(results) - len(success)}")


async def process_single_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Redis worker interface — nhận request dict, trả về result dict."""
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


async def main():
    print("\n" + "=" * 70)
    print("🚀 AMAZON SCRAPER — Playwright + pyvirtualdisplay")
    print("=" * 70)

    urls = read_urls(INPUT_FILE)
    if not urls:
        return

    proxies = load_proxies_from_excel()
    total = len(urls)
    results = []

    for idx, url in enumerate(urls, 1):
        print(f"\n{'─' * 70}")
        print(f"📦 [{idx}/{total}] {url[:80]}")
        result = await process_single_request(url, proxies)
        status = result.get('status', 'failed')
        print(f"   {'✅' if status == 'success' else '❌'} {status.upper()}")
        results.append(result)

    save_results(list(results))
    print("\n✅ HOÀN TẤT!")


if __name__ == "__main__":
    asyncio.run(main())
