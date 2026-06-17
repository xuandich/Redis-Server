"""
RQ Orchestrator - Auto-discover domains and spawn worker threads

Architecture:
  - Scan workers/ folder for domain directories (with Dockerfile)
  - For each domain: create RQ worker thread listening to crawler:{domain} queue
  - Dynamically spawn workers on-demand per job
  - Per-domain concurrency limit (configurable via .env)
"""

import sys
from pathlib import Path
from threading import Thread
from rq import Worker, Queue
import redis as redis_lib

from config import REDIS_HOST, REDIS_PORT, get_max_concurrent

redis_client = redis_lib.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

MAX_CONCURRENT_TOTAL = 10  # Global slot limit


class ThreadSafeWorker(Worker):
    """Worker safe for spawned threads - skips signal handlers
    Also checks global slot availability before picking jobs
    """
    def _install_signal_handlers(self):
        """Skip signal installation - safe for threads"""
        pass

    def monitor_work_horse(self, _job, _queue):
        """Skip death penalty monitoring - safe for threads"""
        pass



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


def start_worker_for_domain(domain):
    """RQ Worker for a specific domain - listens to crawler:{domain} queue

    Worker config:
    - default_result_ttl: 3600 (keep result 1 hour)
    - job_monitoring_interval: 5 (check job health every 5s)
    - Concurrency: Limited by MAX_CONCURRENT_{DOMAIN} from .env
    """
    queue_name = f'crawler:{domain}'
    queue = Queue(queue_name, connection=redis_client)

    max_concurrent = get_max_concurrent(domain)

    worker = ThreadSafeWorker(
        [queue],
        connection=redis_client,
        name=f'worker-{domain}',
        default_result_ttl=3600,  # Keep job results 1 hour
        job_monitoring_interval=5,  # Check job health every 5s
    )

    print(f"[{domain.upper()} Worker] Listening to queue: {queue_name}")
    print(f"  - Max concurrent jobs: {max_concurrent}")
    print(f"  - Job timeout: 180s (from test_job.py)")
    print(f"  - Container timeout: 120s (from .env JOB_TIMEOUT)")
    worker.work()


def cleanup_stale_workers(domains):
    """Remove stale worker registrations and slot counters from previous crashes"""
    for domain in domains:
        worker_key = f'rq:worker:worker-{domain}'
        try:
            if redis_client.exists(worker_key):
                redis_client.delete(worker_key)
                print(f"[Cleanup] Removed stale worker: worker-{domain}")
        except Exception:
            pass

    # Reset slot counters — any leftover slots are stale after restart
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match=b'slots:*', count=100)
        for key in keys:
            redis_client.set(key, 0)
            print(f"[Cleanup] Reset slot: {key.decode()}")
        if cursor == 0:
            break


def start_orchestrator():
    """Auto-discover domains and start worker threads for each"""
    domains = discover_worker_domains()

    print("=" * 60)
    print("Orchestrator started")
    print(f"Discovered domains: {', '.join(domains)}")
    print("=" * 60)

    if not domains:
        print("[Warning] No worker domains found in workers/")
        return

    # Clean up stale workers from previous crashes
    cleanup_stale_workers(domains)

    # Start worker thread for each domain
    threads = []
    for domain in domains:
        thread = Thread(target=start_worker_for_domain, args=(domain,), daemon=True)
        thread.start()
        threads.append(thread)

    # Keep main thread alive
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\nOrchestrator shutting down...")
        sys.exit(0)


if __name__ == '__main__':
    start_orchestrator()
