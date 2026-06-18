#!/usr/bin/env python3
"""
Batch test script via API: Load URLs từ Excel và gửi N requests qua HTTP
Usage: python test_api_batch.py [num_requests] [proxy_type]
  num_requests: số requests (default: 100)
  proxy_type: 'standard' (default) hoặc 'none'

Features:
  - Load URLs from TEST_FILE/fnac_urls.xlsx (same as test_batch.py)
  - Send N random requests via HTTP API (simulating PHP client)
  - Monitor realtime with results
  - Save results to JSON
"""

import pandas as pd
import requests
import json
import time
import uuid
import sys
import random
from datetime import datetime

REDIS_API_URL = 'http://localhost:5000/api/submit-job'
RESULT_POLL_URL = 'http://localhost:5000/api/job'

# Parameters
num_requests = int(sys.argv[1]) if len(sys.argv) > 1 else 100
proxy_type = sys.argv[2] if len(sys.argv) > 2 else 'standard'

# Load URLs from Excel (same as test_batch.py)
print("📂 Loading URLs from TEST_FILE/fnac_urls.xlsx...")
try:
    df = pd.read_excel('TEST_FILE/fnac_urls.xlsx')
    # Assume first column contains URLs
    all_urls = df.iloc[:, 0].dropna().tolist()
    print(f"✅ Loaded {len(all_urls)} URLs")
except Exception as e:
    print(f"❌ Error loading file: {e}")
    sys.exit(1)

if len(all_urls) < num_requests:
    print(f"⚠️  File has only {len(all_urls)} URLs, requesting {num_requests}")
    print(f"    Will sample with replacement")
    selected_urls = [random.choice(all_urls) for _ in range(num_requests)]
else:
    print(f"🎲 Randomly selecting {num_requests} URLs from {len(all_urls)}")
    selected_urls = random.sample(all_urls, num_requests)

print(f"\n📊 Test Configuration:")
print(f"  Proxy: {proxy_type}")
print(f"  Requests: {num_requests}")
print(f"  API URL: {REDIS_API_URL}")
print(f"\n⏱️  Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# Send jobs via API
jobs = []
start_time = time.time()

print(f"\n🚀 Submitting {num_requests} jobs via API...\n")
for i, url in enumerate(selected_urls, 1):
    ret_key = str(uuid.uuid4())

    payload = {
        'url': url,
        'mode': 'none',
        'proxy_type': proxy_type,
        'ret_key': ret_key
    }

    try:
        response = requests.post(REDIS_API_URL, json=payload, timeout=5)

        if response.status_code in [200, 202]:
            result = response.json()
            jobs.append({
                'ret_key': ret_key,
                'url': url,
                'status': 'submitted',
                'submitted_at': time.time()
            })

            if i % 10 == 0:
                print(f"  [{i:3d}/{num_requests}] Submitted")
        else:
            print(f"  [{i:3d}/{num_requests}] Error {response.status_code}")
    except Exception as e:
        print(f"  [{i:3d}/{num_requests}] Error: {str(e)}")

submit_time = time.time() - start_time
print(f"\n✅ Submitted {len(jobs)} jobs in {submit_time:.1f}s")

# Poll results
print("\n" + "=" * 70)
print("📊 Waiting for results...\n")

results = {}
timeout = 600  # 10 minutes timeout
poll_start = time.time()
completed = 0
failed = 0

while time.time() - poll_start < timeout:
    for job in jobs:
        if job['ret_key'] in results:
            continue

        try:
            response = requests.get(f"{RESULT_POLL_URL}/{job['ret_key']}", timeout=5)

            if response.status_code == 200:
                job_result = response.json()
                results[job['ret_key']] = job_result
                job['completed_at'] = time.time()

                status = job_result.get('status', 'unknown')
                http_code = job_result.get('http_code', 0)
                html_size = len(job_result.get('html', ''))
                elapsed = job_result.get('total_elapsed_seconds', 0)

                if status == 'success':
                    completed += 1
                    symbol = '✅' if http_code == 200 else '⚠️'
                    print(f"  {symbol} [{completed + failed:3d}/{num_requests}] HTTP {http_code} | {html_size:6d}B | {elapsed:6.1f}s", flush=True)
                else:
                    failed += 1
                    error_msg = job_result.get('error', 'Unknown error')[:50]
                    print(f"  ❌ [{completed + failed:3d}/{num_requests}] {error_msg}", flush=True)
        except requests.RequestException:
            pass

    if completed + failed >= num_requests:
        break

    # Show progress every 10 seconds
    elapsed = time.time() - poll_start
    print(f"  ⏳ [{completed + failed}/{num_requests}] waiting... ({elapsed:.0f}s)", flush=True)
    time.sleep(2)

# Summary
total_time = time.time() - start_time
print("\n" + "=" * 70)
print("📈 TEST SUMMARY\n")
print(f"Total requests: {num_requests}")
print(f"Submitted: {len(jobs)}")
print(f"Completed: {completed + failed}")
print(f"Success: {completed}")
print(f"Failed: {failed}")
print(f"Total time: {total_time:.1f}s")
if completed + failed > 0:
    print(f"Avg time/request: {total_time/(completed + failed):.1f}s")

# Success rate
success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
print(f"Success rate: {success_rate:.1f}%")

# HTTP code distribution
http_codes = {}
for result in results.values():
    code = result.get('http_code', 0)
    http_codes[code] = http_codes.get(code, 0) + 1

if http_codes:
    print(f"\nHTTP Code Distribution:")
    for code in sorted(http_codes.keys()):
        count = http_codes[code]
        pct = (count / (completed + failed) * 100) if (completed + failed) > 0 else 0
        print(f"  HTTP {code}: {count:3d} ({pct:.1f}%)")

# Save results
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = f"batch_results_api_{timestamp}.json"

output_data = {
    'config': {
        'proxy_type': proxy_type,
        'num_requests': num_requests,
        'timestamp': timestamp,
        'method': 'HTTP API (simulating PHP)',
    },
    'summary': {
        'submitted': len(jobs),
        'completed': completed,
        'failed': failed,
        'success_rate': success_rate,
        'total_time': total_time,
        'avg_time': total_time / (completed + failed) if (completed + failed) > 0 else 0,
    },
    'http_codes': http_codes,
    'results': results,
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)

print(f"\n💾 Results saved to: {output_file}")
print("\n✅ Test completed!")
