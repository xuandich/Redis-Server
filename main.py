import docker
import redis as redis_lib
import json
import time

from config import (
    REDIS_HOST, REDIS_PORT, CRAWLER_NETWORK, PROXY_HOST_DIR,
    CHROMIUM_SNAP_DIR, CHROMIUM_PATH_IN_CONTAINER, JOB_TIMEOUT,
    CONTAINER_MEM_LIMIT, CONTAINER_SHM_SIZE, RESULT_TTL, get_max_concurrent,
    MAX_CONCURRENT_TOTAL
)

redis_client = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
docker_client = docker.from_env()


_LUA_ACQUIRE = """
local key = KEYS[1]
local max_slots = tonumber(ARGV[1])
local current = tonumber(redis.call('GET', key) or 0)
if current < max_slots then
    redis.call('INCR', key)
    redis.call('EXPIRE', key, 3600)
    return 1
end
return 0
"""


def _acquire_slot(slot_type: str, key: str, max_slots: int, timeout: int = 300) -> bool:
    """Acquire a slot using Lua script (atomic, works across processes)"""
    redis_key = f"slots:{slot_type}:{key}"
    start_time = time.time()

    # Lazy register script (ensures Redis is ready)
    lua_acquire = redis_client.register_script(_LUA_ACQUIRE)

    while time.time() - start_time < timeout:
        try:
            if lua_acquire(keys=[redis_key], args=[max_slots]):
                return True
        except Exception as e:
            print(f"[ERROR] Slot acquire failed: {e}", flush=True)
            return False
        time.sleep(0.05)  # Poll every 50ms

    return False


def _release_slot(slot_type: str, key: str):
    """Release a slot using Redis"""
    redis_key = f"slots:{slot_type}:{key}"
    redis_client.decr(redis_key)


def crawl_job(url: str, domain: str, ret_key: str, proxy_type: str = 'standard') -> dict:
    """Crawl job with dual concurrency limits (Redis-based):
    - Global: max total containers across all domains
    - Per-domain: max containers per domain
    """
    job_id = ret_key[:8]

    # 1. Wait for global slot
    max_total = MAX_CONCURRENT_TOTAL
    print(f"[CRAWL_JOB] {domain} {job_id} - START, waiting for global slot (max {max_total})...", flush=True)
    if not _acquire_slot('global', 'total', max_total):
        print(f"[CRAWL_JOB] {domain} {job_id} - GLOBAL TIMEOUT", flush=True)
        error_result = {'status': 'failed', 'error': 'Global slot timeout', 'ret_key': ret_key, 'domain': domain}
        redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
        return error_result

    try:
        # 2. Wait for domain-specific slot
        max_domain = get_max_concurrent(domain)
        print(f"[CRAWL_JOB] {domain} {job_id} - waiting for domain slot (max {max_domain})...", flush=True)
        if not _acquire_slot('domain', domain, max_domain):
            print(f"[CRAWL_JOB] {domain} {job_id} - DOMAIN TIMEOUT", flush=True)
            error_result = {'status': 'failed', 'error': 'Domain slot timeout', 'ret_key': ret_key, 'domain': domain}
            redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
            return error_result

        try:
            print(f"[CRAWL_JOB] {domain} {job_id} - ACQUIRED SLOTS, spawning container...", flush=True)
            result = _spawn_and_wait_container(url, domain, ret_key, proxy_type)
            # Write result to Redis (for test_batch.py polling)
            redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(result, ensure_ascii=False, default=str))
            print(f"[CRAWL_JOB] {domain} {job_id} - CONTAINER DONE", flush=True)
            return result
        finally:
            _release_slot('domain', domain)
            print(f"[CRAWL_JOB] {domain} {job_id} - released domain slot", flush=True)
    finally:
        _release_slot('global', 'total')
        print(f"[CRAWL_JOB] {domain} {job_id} - released global slot", flush=True)


def _spawn_and_wait_container(url: str, domain: str, ret_key: str, proxy_type: str) -> dict:
    """Actually spawn container and wait for result"""
    volumes = {
        CHROMIUM_SNAP_DIR: {'bind': CHROMIUM_SNAP_DIR, 'mode': 'ro'},
    }
    if PROXY_HOST_DIR:
        volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}

    container = docker_client.containers.run(
        f'worker-{domain}:latest',
        environment={
            'URL': url,
            'RET_KEY': ret_key,
            'PROXY_TYPE': proxy_type,
            'REDIS_HOST': REDIS_HOST,
            'REDIS_PORT': str(REDIS_PORT),
            'RESULT_TTL': str(RESULT_TTL),
            'PROXY_DIR': '/app/Proxy',
            'CHROMIUM_PATH': CHROMIUM_PATH_IN_CONTAINER,
        },
        network=CRAWLER_NETWORK,
        volumes=volumes,
        detach=True,
        remove=True,
        mem_limit=CONTAINER_MEM_LIMIT,
        shm_size=CONTAINER_SHM_SIZE,
        cap_add=['SYS_ADMIN'],
    )
    try:
        container.wait(timeout=JOB_TIMEOUT)
        print(f"[{domain}] Container {container.short_id} finished")
    except Exception as e:
        # Timeout or error → kill container immediately
        print(f"[{domain}] Container error: {e}")
        try:
            container.kill()
            print(f"[{domain}] Container killed")
        except:
            pass
        error_result = {
            'url': url,
            'ret_key': ret_key,
            'domain': domain,
            'error': f'Container timeout/error: {str(e)}',
            'status': 'failed'
        }
        redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
        return error_result

    # Fetch result from Redis
    result = redis_client.get(f"result:{ret_key}")
    if result:
        return json.loads(result)

    # No result returned by container
    error_msg = 'No result from container (timeout or crash)'
    print(f"[{domain}] {error_msg}")
    error_result = {
        'url': url,
        'ret_key': ret_key,
        'domain': domain,
        'error': error_msg,
        'status': 'failed'
    }
    redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
    return error_result
