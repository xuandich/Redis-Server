import docker
import redis as redis_lib
import json
from threading import Semaphore

from config import (
    REDIS_HOST, REDIS_PORT, CRAWLER_NETWORK, PROXY_HOST_DIR,
    CHROMIUM_SNAP_DIR, CHROMIUM_PATH_IN_CONTAINER, JOB_TIMEOUT,
    CONTAINER_MEM_LIMIT, CONTAINER_SHM_SIZE, RESULT_TTL, get_max_concurrent,
    MAX_CONCURRENT_TOTAL
)

redis_client = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
docker_client = docker.from_env()

# Global semaphore (limit total concurrent jobs across all domains)
_global_semaphore = Semaphore(MAX_CONCURRENT_TOTAL)

# Per-domain semaphores (limit concurrent jobs per domain)
_domain_semaphores = {}


def _get_semaphore_for_domain(domain: str) -> Semaphore:
    """Get or create semaphore for domain concurrency control"""
    if domain not in _domain_semaphores:
        max_concurrent = get_max_concurrent(domain)
        _domain_semaphores[domain] = Semaphore(max_concurrent)
        print(f"[{domain}] Semaphore created (max_concurrent={max_concurrent})")
    return _domain_semaphores[domain]


def crawl_job(url: str, domain: str, ret_key: str, proxy_type: str = 'standard') -> dict:
    """Crawl job with dual concurrency limits:
    - Global: max total containers across all domains
    - Per-domain: max containers per domain
    """
    job_id = ret_key[:8]

    # 1. Wait for global slot (all domains combined)
    print(f"[{domain}] Job {job_id} waiting for global slot...")
    _global_semaphore.acquire()
    try:
        # 2. Wait for domain-specific slot
        domain_semaphore = _get_semaphore_for_domain(domain)
        print(f"[{domain}] Job {job_id} waiting for domain slot...")
        domain_semaphore.acquire()
        try:
            print(f"[{domain}] Job {job_id} acquired both slots, spawning container...")
            return _spawn_and_wait_container(url, domain, ret_key, proxy_type)
        finally:
            domain_semaphore.release()
            print(f"[{domain}] Job {job_id} released domain slot")
    finally:
        _global_semaphore.release()
        print(f"[{domain}] Job {job_id} released global slot")


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
        return {
            'url': url,
            'ret_key': ret_key,
            'domain': domain,
            'error': f'Container timeout/error: {str(e)}',
            'status': 'failed'
        }

    # Fetch result from Redis
    result = redis_client.get(f"result:{ret_key}")
    if result:
        return json.loads(result)

    # No result returned by container
    error_msg = 'No result from container (timeout or crash)'
    print(f"[{domain}] {error_msg}")
    return {
        'url': url,
        'ret_key': ret_key,
        'domain': domain,
        'error': error_msg,
        'status': 'failed'
    }
