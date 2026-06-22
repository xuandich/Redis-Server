"""
Configuration for Redis Crawler System

Hierarchy:
1. Environment variables (from .env via docker-compose or start.sh)
2. Defaults below

Configure in: .env file
"""
import os

# ========== Redis (from .env) ==========
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

# ========== Docker & Network (from .env) ==========
CRAWLER_NETWORK = os.environ.get('CRAWLER_NETWORK', 'crawler-net')
PROXY_HOST_DIR = os.environ.get('PROXY_HOST_DIR', '')

# ========== Chromium (fixed paths) ==========
CHROMIUM_SNAP_DIR = '/snap/chromium/current'
CHROMIUM_PATH_IN_CONTAINER = '/snap/chromium/current/usr/lib/chromium-browser/chrome'

# ========== Job Configuration (from .env) ==========
RESULT_TTL = int(os.environ.get('RESULT_TTL', 3600))
JOB_TIMEOUT_DEFAULT = int(os.environ.get('JOB_TIMEOUT_DEFAULT', 120))
CONTAINER_MEM_LIMIT = os.environ.get('CONTAINER_MEM_LIMIT', '1g')
CONTAINER_SHM_SIZE = os.environ.get('CONTAINER_SHM_SIZE', '2g')

# ========== Worker Configuration ==========
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', 3))
RETRY_DELAY = 5  # seconds between retries

# ========== Concurrency Limits (from .env) ==========
MAX_CONCURRENT_TOTAL = int(os.environ.get('MAX_CONCURRENT_TOTAL', 10))
MAX_CONCURRENT_FNAC = int(os.environ.get('MAX_CONCURRENT_FNAC', 5))
MAX_CONCURRENT_AMAZON = int(os.environ.get('MAX_CONCURRENT_AMAZON', 3))

def get_max_concurrent(domain: str) -> int:
    """Get max concurrent jobs for a specific domain"""
    return int(os.environ.get(f'MAX_CONCURRENT_{domain.upper()}', 5))

def get_job_timeout(domain: str) -> int:
    """Get job timeout for a specific domain, fallback to JOB_TIMEOUT_DEFAULT"""
    return int(os.environ.get(f'JOB_TIMEOUT_{domain.upper()}', JOB_TIMEOUT_DEFAULT))

# ========== Queues ==========
QUEUE_FNAC = 'crawler:fnac'
QUEUE_AMAZON = 'crawler:amazon'
QUEUE_NEWARK = 'crawler:newark'

# ========== Proxy Configuration ==========
PROXY_TYPE_STANDARD = 'standard'
PROXY_TYPE_NONE = 'none'
