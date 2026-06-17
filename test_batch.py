#!/usr/bin/env python3
"""
Batch test script: Load URLs từ Excel và gửi N requests ngẫu nhiên
Usage: python test_batch.py [num_requests] [domain] [proxy_type]
  num_requests: số requests (default: 100)
  domain: 'fnac' (default) hoặc 'amazon'
  proxy_type: 'standard' (default) hoặc 'none'

Features:
  - Load URLs from TEST_FILE/fnac_urls.xlsx
  - Send N random requests
  - Monitor realtime with worker logs
  - Save results to JSON + worker logs
"""

import pandas as pd
import redis
import json
import time
import uuid
import sys
import random
from rq import Queue
from config import REDIS_HOST, REDIS_PORT, QUEUE_FNAC, QUEUE_AMAZON
from datetime import datetime
from pathlib import Path

# Parameters
num_requests = int(sys.argv[1]) if len(sys.argv) > 1 else 100
domain = sys.argv[2] if len(sys.argv) > 2 else 'fnac'
proxy_type = sys.argv[3] if len(sys.argv) > 3 else 'standard'

# Load URLs from Excel
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

# Connect to Redis (decode_responses=False — consistent with test_job.py and RQ)
queue_map = {'fnac': QUEUE_FNAC, 'amazon': QUEUE_AMAZON}
queue_name = queue_map.get(domain, QUEUE_FNAC)
conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
q = Queue(queue_name, connection=conn)

print(f"\n📊 Test Configuration:")
print(f"  Domain: {domain}")
print(f"  Queue: {queue_name}")
print(f"  Proxy: {proxy_type}")
print(f"  Requests: {num_requests}")
print(f"\n⏱️  Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# Send jobs — enqueue individually like test_job.py (no manual job_state)
jobs = []
ret_keys = []
start_time = time.time()

print(f"\n🚀 Enqueuing {num_requests} jobs...\n")
for i, url in enumerate(selected_urls, 1):
    ret_key = str(uuid.uuid4())
    ret_keys.append(ret_key)

    try:
        job_timeout = num_requests * 30  # 30s per request

        job = q.enqueue(
            'main.crawl_job',
            url=url,
            domain=domain,
            ret_key=ret_key,
            proxy_type=proxy_type,
            job_timeout=job_timeout,
        )

        jobs.append((job.id, ret_key, url))

        if i % 10 == 0:
            print(f"  [{i:3d}/{num_requests}] Enqueued")
    except Exception as e:
        print(f"  [{i:3d}/{num_requests}] Error: {e}")

enqueue_time = time.time() - start_time
print(f"\n✅ All {num_requests} jobs enqueued in {enqueue_time:.1f}s")

# Poll results
print("\n" + "=" * 70)
print("📊 Waiting for results...\n")

results = {}
worker_logs = {}
timeout = 600  # 10 minutes timeout
poll_start = time.time()
completed = 0
failed = 0
show_logs = True  # Show worker logs in realtime

def load_worker_log(ret_key: str) -> str:
    """Load worker log if exists"""
    log_file = Path('logs/worker') / f"{ret_key[:8]}.log"
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

while time.time() - poll_start < timeout:
    for job_id, ret_key, url in jobs:
        if ret_key in results:
            continue

        try:
            value = conn.get(f'result:{ret_key}')
            if value:
                result = json.loads(value)
                results[ret_key] = result

                status = result.get('status', 'unknown')
                http_code = result.get('http_code', 0)
                html_size = len(result.get('html', ''))
                elapsed = result.get('total_elapsed_seconds', 0)

                # Try to load worker logs
                worker_log = load_worker_log(ret_key)
                if worker_log:
                    worker_logs[ret_key] = worker_log

                if status == 'success':
                    completed += 1
                    symbol = '✅' if http_code == 200 else '⚠️'
                    print(f"  {symbol} [{completed + failed:3d}/{num_requests}] HTTP {http_code} | {html_size:6d}B | {elapsed:6.1f}s", flush=True)
                else:
                    failed += 1
                    error_msg = result.get('error', 'Unknown error')[:50]
                    print(f"  ❌ [{completed + failed:3d}/{num_requests}] {error_msg}", flush=True)

                # Show logs if enabled
                if show_logs and worker_log:
                    first_line = worker_log.split(chr(10))[0]
                    print(f"     [LOGS] {first_line}", flush=True)
        except Exception as e:
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
print(f"Completed: {completed + failed}")
print(f"Success: {completed}")
print(f"Failed: {failed}")
print(f"Total time: {total_time:.1f}s")
print(f"Avg time/request: {total_time/num_requests:.1f}s")

# Success rate
success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
print(f"Success rate: {success_rate:.1f}%")

# HTTP code distribution
http_codes = {}
for result in results.values():
    code = result.get('http_code', 0)
    http_codes[code] = http_codes.get(code, 0) + 1

print(f"\nHTTP Code Distribution:")
for code in sorted(http_codes.keys()):
    count = http_codes[code]
    pct = (count / (completed + failed) * 100) if (completed + failed) > 0 else 0
    print(f"  HTTP {code}: {count:3d} ({pct:.1f}%)")

# Save results
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = f"batch_results_{timestamp}.json"

# Prepare output data
output_data = {
    'config': {
        'domain': domain,
        'proxy_type': proxy_type,
        'num_requests': num_requests,
        'timestamp': timestamp,
    },
    'summary': {
        'completed': completed,
        'failed': failed,
        'success_rate': success_rate,
        'total_time': total_time,
        'avg_time': total_time / num_requests,
    },
    'http_codes': http_codes,
    'results': {k: v for k, v in results.items()},
    'worker_logs': worker_logs,  # Include worker logs
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)

print(f"\n💾 Results saved to: {output_file}")

# Also save separate log files for debugging
if worker_logs:
    logs_dir = Path('logs/batch') / timestamp
    logs_dir.mkdir(parents=True, exist_ok=True)
    for ret_key, log_content in worker_logs.items():
        log_file = logs_dir / f"{ret_key[:8]}.log"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(log_content)
    print(f"📁 Worker logs saved to: {logs_dir}/")

print("\n✅ Test completed!")
