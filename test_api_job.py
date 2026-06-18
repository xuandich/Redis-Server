#!/usr/bin/env python3
"""
Test API submission (simulate PHP client)
Usage: python test_api_job.py [url] [proxy_type]
  proxy_type: 'standard' (default) hoặc 'none'
"""

import requests
import json
import time
import uuid
import sys

REDIS_API_URL = 'http://localhost:5000/api/submit-job'
RESULT_POLL_URL = 'http://localhost:5000/api/job'

TEST_URL = 'https://www.fnac.com/Kit-creatif-avec-Gouache-Lefranc-Bourgeois-Toiles-de-Maitres/a17346494/w-4'

url = sys.argv[1] if len(sys.argv) > 1 else TEST_URL
proxy_type = sys.argv[2] if len(sys.argv) > 2 else 'standard'
ret_key = str(uuid.uuid4())

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

                output_file = f"result_{ret_key[:8]}.json"
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
