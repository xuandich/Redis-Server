# BUG-41: docker_client timeout cứng theo JOB_TIMEOUT_DEFAULT — không cover per-domain timeout dài hơn

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-22

## Problem

`docker_client` được khởi tạo một lần tại import time với `timeout=JOB_TIMEOUT_DEFAULT + 120`. Với `JOB_TIMEOUT_DEFAULT=120`, socket timeout của HTTP client = 240s. Nếu thêm domain mới có `JOB_TIMEOUT_{DOMAIN}` lớn hơn 240s (ví dụ 600s, 900s), các Docker API call không phải `wait()` (như `images.get()`, `containers.run()`, `container.kill()`) bị giới hạn ở 240s — Docker daemon treo lâu hơn sẽ bị cut off sớm.

Ngoài ra, `container.wait(timeout=N)` của docker SDK **override** socket timeout cho request đó, nên `wait(timeout=720)` vẫn hoạt động đúng. Bug ảnh hưởng các API call thông thường khác khi daemon gặp vấn đề.

### Root Cause

[main.py:15](main.py#L15):
```python
docker_client = docker.from_env(timeout=JOB_TIMEOUT_DEFAULT + 120)
```

- Khởi tạo 1 lần tại module load
- Dùng `JOB_TIMEOUT_DEFAULT` (120s) thay vì max timeout across tất cả domains
- Các domain có timeout lớn hơn (newark: 720s) không được reflect vào client-level timeout

## Scenario

```
JOB_TIMEOUT_DEFAULT=120 → docker_client timeout=240s
JOB_TIMEOUT_NEWARK=720

Docker daemon bị treo (OOM, disk full, v.v.)
container.kill() gọi sau timeout trong newark job
→ Docker API call hang > 240s
→ docker_client HTTP socket timeout cut off sau 240s
→ kill() raise exception, container không được kill
→ orphan container chạy tiếp đến hết JOB_TIMEOUT_NEWARK
```

## Impact

- LOW: chỉ xảy ra khi Docker daemon gặp sự cố (uncommon)
- `container.wait(timeout=N)` không bị ảnh hưởng (SDK override per-request)
- Chủ yếu ảnh hưởng `container.kill()` và các admin operations khi daemon chậm

## Fix

Tính max timeout từ tất cả domain configs:
```python
import os

def _max_job_timeout() -> int:
    """Max job timeout across all configured domains"""
    max_t = JOB_TIMEOUT_DEFAULT
    for key, val in os.environ.items():
        if key.startswith('JOB_TIMEOUT_') and key != 'JOB_TIMEOUT_DEFAULT':
            try:
                max_t = max(max_t, int(val))
            except ValueError:
                pass
    return max_t

docker_client = docker.from_env(timeout=_max_job_timeout() + 120)
```

Kết quả: với `JOB_TIMEOUT_NEWARK=720`, `docker_client timeout = 840s`.

## Test

```bash
# Với JOB_TIMEOUT_NEWARK=720, check docker_client timeout hiện tại:
python3 -c "
import os; os.environ['JOB_TIMEOUT_DEFAULT']='120'
import docker
c = docker.from_env(timeout=120+120)
print(c.api.timeout)  # ❌ 240 — không cover 720s
"
```
