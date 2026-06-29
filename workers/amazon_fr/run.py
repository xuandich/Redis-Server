import asyncio
import os
import json
import sys
import redis

url = os.environ.get('URL', '')
ret_key = os.environ.get('RET_KEY', '')
proxy_type = os.environ.get('PROXY_TYPE', 'standard')
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_port = int(os.environ.get('REDIS_PORT', 6379))
result_ttl = int(os.environ.get('RESULT_TTL', 3600))


def write_error_to_redis(error_msg: str):
    try:
        r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        result = {
            'url': url, 'ret_key': ret_key, 'status': 'failed',
            'error': error_msg, 'http_code': None,
            'html': '', 'headers': {}, 'cookies': {},
            'elapsed_ms': 0, 'proxy_type': proxy_type, 'total_elapsed_seconds': 0,
        }
        r.setex(f"result:{ret_key}", result_ttl, json.dumps(result, ensure_ascii=False, default=str))
        print(f"[AMAZON_FR] Error written to Redis: {error_msg}")
    except Exception as redis_err:
        print(f"[AMAZON_FR] Could not write error to Redis: {redis_err}")


try:
    sys.path.insert(0, '/app/sourceCode')
    from main import process_single_request
except Exception as import_err:
    print(f"[AMAZON_FR] Import error: {import_err}")
    write_error_to_redis(f"Import error: {import_err}")
    sys.exit(1)


async def main():
    r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    try:
        request = {'url': url, 'ret_key': ret_key, 'proxy_type': proxy_type}
        result = await process_single_request(request)
    except Exception as e:
        result = {
            'url': url, 'ret_key': ret_key, 'status': 'failed',
            'error': f'Worker exception: {str(e)}',
            'http_code': None, 'html': '', 'headers': {}, 'cookies': {},
            'elapsed_ms': 0, 'proxy_type': proxy_type, 'total_elapsed_seconds': 0,
        }
        print(f"[AMAZON_FR] Exception: {e}")

    print(f"[AMAZON_FR] status={result.get('status')} http={result.get('http_code')} error={result.get('error')} html_len={len(result.get('html') or '')}")
    r.setex(f"result:{ret_key}", result_ttl, json.dumps(result, ensure_ascii=False, default=str))
    print(f"[AMAZON_FR] Done: {ret_key}")


if __name__ == '__main__':
    asyncio.run(main())
