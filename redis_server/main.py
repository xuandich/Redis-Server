import docker
import redis as redis_lib
import json
import time

from config import (
    REDIS_HOST, REDIS_PORT, CRAWLER_NETWORK, PROXY_HOST_DIR,
    CHROMIUM_SNAP_DIR, CHROMIUM_PATH_IN_CONTAINER, JOB_TIMEOUT_DEFAULT,
    CONTAINER_MEM_LIMIT, CONTAINER_SHM_SIZE, RESULT_TTL, get_max_concurrent,
    get_job_timeout, MAX_CONCURRENT_TOTAL
)

redis_client = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
# Timeout must exceed JOB_TIMEOUT_DEFAULT so container.wait() isn't cut off by HTTP socket timeout
docker_client = docker.from_env(timeout=JOB_TIMEOUT_DEFAULT + 120)

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


def _acquire_slot(slot_type: str, key: str, max_slots: int, timeout: int = 60) -> bool:
    """Acquire a slot using Lua script (atomic, cross-process safe)"""
    redis_key = f"slots:{slot_type}:{key}"
    start_time = time.time()
    lua_acquire = redis_client.register_script(_LUA_ACQUIRE)
    while time.time() - start_time < timeout:
        try:
            if lua_acquire(keys=[redis_key], args=[max_slots]):
                return True
        except Exception as e:
            print(f"[ERROR] Slot acquire failed: {e}", flush=True)
            return False
        time.sleep(0.05)
    return False


def _release_slot(slot_type: str, key: str):
    """Release a slot"""
    redis_key = f"slots:{slot_type}:{key}"
    val = redis_client.decr(redis_key)
    if val < 0:
        redis_client.set(redis_key, 0)


def _set_job_state(ret_key: str, state: str, url: str, domain: str, proxy_type: str = 'standard', ttl: int = 86400):
    """Set job state for dashboard tracking"""
    redis_client.setex(f"job_state:{ret_key}", ttl, json.dumps({
        'ret_key': ret_key,
        'state': state,
        'url': url,
        'domain': domain,
        'proxy_type': proxy_type,
        'timestamp': time.time()
    }, ensure_ascii=False, default=str))


def _clear_job_state(ret_key: str):
    redis_client.delete(f"job_state:{ret_key}")


def crawl_job(url: str, domain: str, ret_key: str, proxy_type: str = 'standard') -> dict:
    job_id = ret_key[:8]

    # Mark as queued immediately (before slot wait, so dashboard shows pending jobs)
    _set_job_state(ret_key, 'queued', url, domain, proxy_type)

    print(f"[CRAWL_JOB] {domain} {job_id} - START, waiting for global slot (max {MAX_CONCURRENT_TOTAL})...", flush=True)
    if not _acquire_slot('global', 'total', MAX_CONCURRENT_TOTAL):
        print(f"[CRAWL_JOB] {domain} {job_id} - GLOBAL TIMEOUT", flush=True)
        error_result = {'status': 'failed', 'error': 'Global slot timeout', 'ret_key': ret_key, 'domain': domain, 'url': url}
        redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
        _clear_job_state(ret_key)
        return error_result

    try:
        max_domain = get_max_concurrent(domain)
        print(f"[CRAWL_JOB] {domain} {job_id} - waiting for domain slot (max {max_domain})...", flush=True)
        if not _acquire_slot('domain', domain, max_domain):
            print(f"[CRAWL_JOB] {domain} {job_id} - DOMAIN TIMEOUT", flush=True)
            error_result = {'status': 'failed', 'error': 'Domain slot timeout', 'ret_key': ret_key, 'domain': domain, 'url': url}
            redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
            _clear_job_state(ret_key)
            return error_result

        _set_job_state(ret_key, 'running', url, domain, proxy_type)

        try:
            print(f"[CRAWL_JOB] {domain} {job_id} - ACQUIRED SLOTS, spawning container...", flush=True)
            result = _spawn_and_wait_container(url, domain, ret_key, proxy_type)
            _clear_job_state(ret_key)
            print(f"[CRAWL_JOB] {domain} {job_id} - CONTAINER DONE", flush=True)
            return result
        except Exception as e:
            print(f"[CRAWL_JOB] {domain} {job_id} - EXCEPTION: {e}", flush=True)
            error_result = {
                'status': 'failed', 'error': str(e),
                'ret_key': ret_key, 'domain': domain, 'url': url,
            }
            redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
            _clear_job_state(ret_key)
            raise
        finally:
            _release_slot('domain', domain)
            print(f"[CRAWL_JOB] {domain} {job_id} - released domain slot", flush=True)
    finally:
        _release_slot('global', 'total')
        print(f"[CRAWL_JOB] {domain} {job_id} - released global slot", flush=True)


def _spawn_and_wait_container(url: str, domain: str, ret_key: str, proxy_type: str) -> dict:
    # Auto-load worker image from cache if missing
    image_name = f'worker-{domain}:latest'
    try:
        docker_client.images.get(image_name)
    except docker.errors.ImageNotFound:
        import os
        cache_file = f'workers/{domain}/worker-{domain}-latest.tar.gz'
        if os.path.exists(cache_file):
            print(f"[{domain}] Loading image from cache: {cache_file}")
            with open(cache_file, 'rb') as f:
                docker_client.images.load(f)
            print(f"[{domain}] Image loaded: {image_name}")
        else:
            error_msg = f'Worker image {image_name} not found'
            return {'url': url, 'ret_key': ret_key, 'domain': domain, 'error': error_msg, 'status': 'failed'}

    volumes = {
        CHROMIUM_SNAP_DIR: {'bind': CHROMIUM_SNAP_DIR, 'mode': 'ro'},
    }
    import os as _os
    # PROXY_HOST_DIR is a host path (for Docker volume mount).
    # Check existence via PROXY_CHECK_DIR (container-internal path to same dir).
    _proxy_check = _os.environ.get('PROXY_CHECK_DIR', PROXY_HOST_DIR)
    if proxy_type == 'standard' and PROXY_HOST_DIR and _os.path.isdir(_proxy_check):
        volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}
    elif proxy_type == 'standard':
        print(f"[{domain}] WARNING: PROXY_HOST_DIR not found ({PROXY_HOST_DIR!r}), running without proxy", flush=True)
        proxy_type = 'none'

    container = docker_client.containers.run(
        image_name,
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
        container.wait(timeout=get_job_timeout(domain))
        print(f"[{domain}] Container {container.short_id} finished")
    except Exception as e:
        print(f"[{domain}] Container error: {e}")
        try:
            container.kill()
        except:
            pass
        error_result = {
            'url': url, 'ret_key': ret_key, 'domain': domain,
            'error': f'Container timeout/error: {str(e)}', 'status': 'failed',
            'timestamp': time.time(),
        }
        redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
        return error_result

    result = redis_client.get(f"result:{ret_key}")
    if result:
        result_dict = json.loads(result)
        result_dict.setdefault('timestamp', time.time())
        return result_dict

    error_result = {
        'url': url, 'ret_key': ret_key, 'domain': domain,
        'error': 'No result from container', 'status': 'failed',
        'timestamp': time.time(),
    }
    redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
    return error_result
