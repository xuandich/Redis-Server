# BUG-34: Concurrent image auto-load — N threads load the same 300MB tar.gz simultaneously

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`_spawn_and_wait_container` check-then-load không có lock. Với MAX_CONCURRENT_FNAC=5 threads chia sẻ 1 `docker_client`, batch đầu sau khi image bị evict → cả 5 threads cùng `ImageNotFound` và cùng stream 300MB tar vào `images.load()` đồng thời → đọc dư thừa 300MB × N, daemon load contention.

### Root Cause

[main.py:112-125](main.py#L112-L125):
```python
try:
    docker_client.images.get(image_name)
except docker.errors.ImageNotFound:
    cache_file = f'workers/{domain}/worker-{domain}-latest.tar.gz'
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as f:
            docker_client.images.load(f)   # ← không lock, N threads cùng load
```
Không có `threading.Lock` gating get/load. Tự self-heal (chỉ batch đầu), threads "thua" vẫn `containers.run` thành công (image đã tồn tại lúc đó).

## Impact

- Đọc dư 300MB × N một lần (batch đầu sau evict)
- Daemon load contention; không corrupt (mỗi load mở file handle riêng, load idempotent)
- Efficiency, không phải correctness

## Fix

Per-image lock:
```python
import threading
_image_load_locks = {}
_locks_guard = threading.Lock()

def _get_image_lock(image_name):
    with _locks_guard:
        return _image_load_locks.setdefault(image_name, threading.Lock())

# trong _spawn_and_wait_container:
with _get_image_lock(image_name):
    try:
        docker_client.images.get(image_name)
    except docker.errors.ImageNotFound:
        ...  # load
```

## Test

```bash
docker rmi worker-fnac:latest
# Submit 5 fnac jobs cùng lúc; theo dõi I/O đọc tar.gz
# ❌ 5 lần đọc 300MB  →  ✅ 1 lần
```
