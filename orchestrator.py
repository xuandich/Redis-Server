"""
RQ Orchestrator - Auto-discover domains and spawn worker threads

Architecture:
  - Scan workers/ folder for domain directories (with Dockerfile)
  - For each domain: spawn MAX_CONCURRENT_{DOMAIN} SimpleWorker threads
  - SimpleWorker runs jobs in-process (no fork) — thread-safe, no zombie, no deadlock
  - Per-domain concurrency = number of worker threads; global limit via slot counter
"""

import sys
import time
from pathlib import Path
from threading import Thread
from rq import SimpleWorker, Queue
from rq.timeouts import TimerDeathPenalty
import redis as redis_lib

from config import REDIS_HOST, REDIS_PORT, get_max_concurrent, MAX_CONCURRENT_TOTAL

redis_client = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)


def _can_acquire_slots(domain: str) -> bool:
    """Kiểm tra global + domain slots có available không"""
    try:
        global_slots = int(redis_client.get('slots:global:total') or 0)
        if global_slots >= MAX_CONCURRENT_TOTAL:
            return False

        max_domain = get_max_concurrent(domain)
        domain_slots = int(redis_client.get(f'slots:domain:{domain}') or 0)
        if domain_slots >= max_domain:
            return False

        return True
    except Exception as e:
        print(f"[ERROR] Slot check failed: {e}", flush=True)
        return False  # Fail-closed: không dequeue khi Redis không ổn định


class ThreadSafeWorker(SimpleWorker):
    """SimpleWorker safe for threads — không fork, không zombie, không deadlock.

    Mỗi instance xử lý 1 job tại 1 thời điểm. Concurrency đạt được bằng cách
    chạy MAX_CONCURRENT_{DOMAIN} instances song song cho mỗi domain.
    """
    # UnixSignalDeathPenalty dùng SIGALRM, chỉ hoạt động trên main thread.
    # TimerDeathPenalty dùng threading.Timer — thread-safe.
    death_penalty_class = TimerDeathPenalty

    def __init__(self, *args, domain=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain

    def _install_signal_handlers(self):
        """Skip signal installation - safe for threads"""
        pass

    def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
        """Check slots TRƯỚC khi dequeue — nếu full thì sleep + heartbeat"""
        while not _can_acquire_slots(self.domain):
            time.sleep(1)
            self.heartbeat()

        return super().dequeue_job_and_maintain_ttl(timeout, max_idle_time)


def discover_worker_domains():
    """Scan workers/ folder for domain directories (must have Dockerfile)"""
    workers_dir = Path(__file__).parent / 'workers'

    if not workers_dir.exists():
        print(f"[Error] {workers_dir} not found")
        return []

    domains = []
    for item in workers_dir.iterdir():
        if item.is_dir() and item.name != 'Proxy':
            dockerfile = item / 'Dockerfile'
            if dockerfile.exists():
                domains.append(item.name)

    return sorted(domains)


def start_worker_for_domain(domain, worker_index):
    """Một SimpleWorker instance cho domain — blocking loop xử lý jobs tuần tự"""
    queue_name = f'crawler:{domain}'
    queue = Queue(queue_name, connection=redis_client)

    worker = ThreadSafeWorker(
        [queue],
        connection=redis_client,
        name=f'worker-{domain}-{worker_index}',
        default_result_ttl=3600,
        job_monitoring_interval=5,
        domain=domain,
    )

    print(f"[{domain.upper()}] Worker-{worker_index} listening on {queue_name}", flush=True)
    worker.work()


def _retry_stale_jobs():
    """Re-enqueue in-flight jobs lost during crash.

    job_state:{ret_key} (queued/running) = job was picked by RQ but not finished.
    Since job_id=ret_key, we can check RQ job status directly.
    Queued jobs never picked by RQ survive in the queue via Redis AOF (docker compose stop).
    """
    import json
    import time
    import main as crawler_main
    from rq.job import Job as RQJob
    from rq.exceptions import NoSuchJobError

    retried = skipped = 0
    cursor = 0

    while True:
        cursor, keys = redis_client.scan(cursor, match=b'job_state:*', count=100)
        for key in keys:
            try:
                value = redis_client.get(key)
                if not value:
                    redis_client.delete(key)
                    continue

                data = json.loads(value)
                state = data.get('state', '')
                ret_key = data.get('ret_key', '')
                url = data.get('url', '')
                domain = data.get('domain', '')
                proxy_type = data.get('proxy_type', 'standard')

                if state not in ('queued', 'running'):
                    redis_client.delete(key)
                    continue

                # Already finished — cleanup job_state
                if redis_client.exists(f'result:{ret_key}'):
                    redis_client.delete(key)
                    skipped += 1
                    continue

                # Check if job is still in RQ queue (truly queued, not yet picked up)
                try:
                    rq_job = RQJob.fetch(ret_key, connection=redis_client)
                    job_status = rq_job.get_status()
                    if job_status == 'queued':
                        skipped += 1
                        continue
                    elif job_status in ('finished', 'failed'):
                        redis_client.delete(key)
                        skipped += 1
                        continue
                    else:
                        try:
                            rq_job.delete()
                        except Exception:
                            pass
                except NoSuchJobError:
                    pass  # Job lost entirely → re-enqueue

                redis_client.delete(key)
                q = Queue(f'crawler:{domain}', connection=redis_client)
                q.enqueue(crawler_main.crawl_job, url, domain, ret_key, proxy_type,
                          job_timeout=600, job_id=ret_key)
                redis_client.setex(f'job_state:{ret_key}', 86400, json.dumps({
                    'state': 'queued',
                    'ret_key': ret_key,
                    'url': url,
                    'domain': domain,
                    'proxy_type': proxy_type,
                    'timestamp': time.time(),
                }))
                retried += 1
                print(f"[Retry] Re-enqueued {ret_key[:8]} ({domain}): {url[:70]}")
            except Exception as e:
                print(f"[Retry] Error processing {key}: {e}")
        if cursor == 0:
            break

    if retried or skipped:
        print(f"[Retry] Re-enqueued={retried}, skipped={skipped}")


def cleanup_stale_workers(domains):
    """Remove stale worker registrations and slot counters from previous crashes"""
    # Xóa tất cả rq:worker:* (tên worker thay đổi qua các lần restart)
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match=b'rq:worker:*', count=100)
        for key in keys:
            redis_client.delete(key)
            print(f"[Cleanup] Removed stale worker: {key.decode()}")
        if cursor == 0:
            break

    # Reset slot counters — any leftover slots are stale after restart
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match=b'slots:*', count=100)
        for key in keys:
            redis_client.delete(key)
            print(f"[Cleanup] Deleted slot: {key.decode()}")
        if cursor == 0:
            break

    _retry_stale_jobs()


def _wait_for_redis(max_retries: int = 30, delay: int = 2):
    """Wait until Redis is reachable before starting"""
    for i in range(max_retries):
        try:
            redis_client.ping()
            print("[Orchestrator] Redis ready", flush=True)
            return
        except Exception as e:
            print(f"[Orchestrator] Waiting for Redis ({i + 1}/{max_retries}): {e}", flush=True)
            time.sleep(delay)
    raise RuntimeError("Redis not available after retries — aborting")


def start_orchestrator():
    """Auto-discover domains and start worker threads for each"""
    _wait_for_redis()

    domains = discover_worker_domains()

    print("=" * 60)
    print("Orchestrator started")
    print(f"Discovered domains: {', '.join(domains)}")
    print("=" * 60)

    if not domains:
        print("[Warning] No worker domains found in workers/")
        return

    cleanup_stale_workers(domains)

    # Spawn MAX_CONCURRENT_{DOMAIN} worker threads per domain
    threads = []
    for domain in domains:
        max_concurrent = get_max_concurrent(domain)
        print(f"[{domain.upper()}] Starting {max_concurrent} worker threads")
        for i in range(max_concurrent):
            thread = Thread(
                target=start_worker_for_domain,
                args=(domain, i),
                daemon=True,
                name=f'worker-{domain}-{i}',
            )
            thread.start()
            threads.append(thread)

    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\nOrchestrator shutting down...")
        sys.exit(0)


if __name__ == '__main__':
    start_orchestrator()
