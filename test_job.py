#!/usr/bin/env python3
"""
Test script: enqueue crawl job và wait result
Usage: python test_job.py [url] [domain] [proxy_type]
  domain: 'fnac' (default) hoặc 'amazon'
  proxy_type: 'standard' (default) hoặc 'none'
"""

import redis
import json
import time
import uuid
import sys
from rq import Queue
from config import REDIS_HOST, REDIS_PORT, QUEUE_FNAC, QUEUE_AMAZON

TEST_URL = 'https://www.fnac.com/Kit-creatif-avec-Gouache-Lefranc-Bourgeois-Toiles-de-Maitres/a17346494/w-4'

url = sys.argv[1] if len(sys.argv) > 1 else TEST_URL
domain = sys.argv[2] if len(sys.argv) > 2 else 'fnac'
proxy_type = sys.argv[3] if len(sys.argv) > 3 else 'standard'
ret_key = str(uuid.uuid4())

# Select queue based on domain
queue_map = {'fnac': QUEUE_FNAC, 'amazon': QUEUE_AMAZON}
queue_name = queue_map.get(domain, QUEUE_FNAC)

conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
q = Queue(queue_name, connection=conn)

print(f"URL       : {url}")
print(f"Domain    : {domain}")
print(f"Proxy     : {proxy_type}")
print(f"Ret_key   : {ret_key}")
print(f"Queue     : {queue_name}")
print(f"Enqueuing job...")

job = q.enqueue(
    'main.crawl_job',
    url=url,
    domain=domain,
    ret_key=ret_key,
    proxy_type=proxy_type,
    job_timeout=180,
    job_id=ret_key,
)

print(f"Job ID : {job.id}")
print("Waiting for result", end='', flush=True)

start = time.time()
while time.time() - start < 180:
    try:
        job.refresh()
    except Exception as e:
        # Ignore connection errors during refresh
        pass

    if job.is_finished:
        result = job.result
        output_file = f"result_{ret_key[:8]}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nDone in {time.time()-start:.1f}s")
        print(f"Status  : {result.get('status')}")
        print(f"HTTP    : {result.get('http_code')}")
        print(f"HTML    : {len(result.get('html') or '')} bytes")
        print(f"Saved   : {output_file}")
        break
    elif job.is_failed:
        print(f"\nJob failed: {job.exc_info}")
        break
    else:
        print('.', end='', flush=True)
        time.sleep(3)
else:
    print("\nTimeout after 180s")
