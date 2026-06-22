import asyncio
import os
import json
import sys
import redis

sys.path.insert(0, '/app/sourceCode')
from main import process_single_request


async def main():
    # Job parameters
    url = os.environ['URL']
    ret_key = os.environ['RET_KEY']
    proxy_type = os.environ.get('PROXY_TYPE', 'standard')

    # Redis config
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    result_ttl = int(os.environ.get('RESULT_TTL', 3600))

    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    try:
        request = {'url': url, 'ret_key': ret_key, 'proxy_type': proxy_type}
        result = await process_single_request(request, asyncio.Semaphore(1))
    except Exception as e:
        result = {
            'url': url,
            'ret_key': ret_key,
            'status': 'failed',
            'error': f'Worker exception: {str(e)}',
            'http_code': None,
            'html': '',
            'headers': {},
            'cookies': {},
            'elapsed_ms': 0,
            'proxy_type': proxy_type,
            'total_elapsed_seconds': 0,
        }
        print(f"[NEWARK] Exception: {e}")

    print(f"[NEWARK] status={result.get('status')} http={result.get('http_code')} error={result.get('error')} html_len={len(result.get('html') or '')}")
    r.setex(f"result:{ret_key}", result_ttl, json.dumps(result, ensure_ascii=False, default=str))
    print(f"[NEWARK] Done: {ret_key}")


if __name__ == '__main__':
    asyncio.run(main())
