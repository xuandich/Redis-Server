#!/usr/bin/env python3
"""
Test API submission (simulate PHP client)
Usage:
  python test_api_job.py                              -> fnac, random URL từ TEST_FILE/fnac_urls.xlsx
  python test_api_job.py [domain]                     -> random URL từ TEST_FILE/{domain}_urls.xlsx
  python test_api_job.py [domain] [proxy_type]        -> random URL, proxy tuỳ chọn
  python test_api_job.py [url] [domain] [proxy_type]  -> URL trực tiếp

ret_key format: ret_{domain}_{uuid}  (ví dụ: ret_newark_550e8400-...)
"""

import requests
import json
import time
import uuid
import sys
import os
import random

REDIS_API_URL = 'http://localhost:5000/api/submit-job'
RESULT_POLL_URL = 'http://localhost:5000/api/job'


def pick_random_url(domain: str) -> str:
    xlsx_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'TEST_FILE', f'{domain}_urls.xlsx')
    if not os.path.exists(xlsx_path):
        print(f"TEST_FILE/{domain}_urls.xlsx not found — dùng URL mặc định")
        return None
    import pandas as pd
    df = pd.read_excel(xlsx_path, header=None)
    urls = df.iloc[:, 0].dropna().tolist()
    if not urls:
        return None
    url = random.choice(urls)
    print(f"Random URL from {domain}_urls.xlsx: {url}")
    return str(url)


# Parse arguments: nếu argv[1] bắt đầu bằng 'http' → URL trực tiếp
if len(sys.argv) > 1 and sys.argv[1].startswith('http'):
    url = sys.argv[1]
    domain = sys.argv[2] if len(sys.argv) > 2 else 'fnac'
    proxy_type = sys.argv[3] if len(sys.argv) > 3 else 'standard'
else:
    domain = sys.argv[1] if len(sys.argv) > 1 else 'fnac'
    proxy_type = sys.argv[2] if len(sys.argv) > 2 else 'standard'
    url = pick_random_url(domain)
    if not url:
        sys.exit(1)

ret_key = f"ret_{domain}_{uuid.uuid4()}"

payload = {
    'url': url,
    'mode': 'none',
    'proxy_type': proxy_type,
    'ret_key': ret_key
}

print(f"URL       : {url}")
print(f"Proxy     : {proxy_type}")
print(f"Ret_key   : {ret_key}")
print(f"API URL   : {REDIS_API_URL}")
print(f"Submitting job...")

try:
    # Submit job via API
    response = requests.post(REDIS_API_URL, json=payload, timeout=5)

    if response.status_code not in [200, 202]:
        print(f"Error: {response.status_code}")
        print(response.text)
        sys.exit(1)

    result = response.json()
    print(f"Job ID    : {result['ret_key_short']}")
    print("Polling for result", end='', flush=True)

    # Poll for result
    start = time.time()
    while time.time() - start < 180:
        try:
            poll_response = requests.get(f"{RESULT_POLL_URL}/{ret_key}", timeout=5)

            if poll_response.status_code == 200:
                job_result = poll_response.json()
                elapsed = time.time() - start

                output_file = f"result_{ret_key.split('_')[-1][:8]}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(job_result, f, ensure_ascii=False, indent=2, default=str)

                print(f"\nDone in {elapsed:.1f}s")
                print(f"Status  : {job_result.get('status')}")
                print(f"HTTP    : {job_result.get('http_code')}")
                print(f"HTML    : {len(job_result.get('html') or '')} bytes")
                print(f"Saved   : {output_file}")
                break
            else:
                print('.', end='', flush=True)
                time.sleep(3)
        except requests.RequestException:
            print('.', end='', flush=True)
            time.sleep(3)
    else:
        print("\nTimeout after 180s")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
