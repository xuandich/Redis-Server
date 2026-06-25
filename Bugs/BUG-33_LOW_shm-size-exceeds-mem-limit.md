# BUG-33: shm_size='2g' exceeds mem_limit='1g' — Chromium OOM-killed with opaque error

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

Worker container chạy với `mem_limit='1g'` nhưng `shm_size='2g'`. `/dev/shm` là tmpfs tính vào memory cgroup của container → cấu hình 2g shm dưới 1g hard limit nghĩa là Chromium ghi `/dev/shm` chạm cgroup limit và bị OOM-kill (exit 137) trước khi dùng hết 2g shm danh nghĩa. Báo generic "No result from container", không lộ OOM.

### Root Cause

[config.py:27-28](config.py#L27-L28):
```python
CONTAINER_MEM_LIMIT = ... '1g'
CONTAINER_SHM_SIZE = ... '2g'
```
[main.py:150-151](main.py#L150-L151) truyền verbatim vào `containers.run(mem_limit=..., shm_size=...)`. tmpfs `/dev/shm` charge vào cgroup → OOM killer fire gần 1g trước. Container exit 137 không raise ở `container.wait()` (xem BUG-21) → fall through → "No result from container".

## Impact

- Conditional: chỉ khi shm pressure cao (trang nặng)
- Operational/diagnosability degradation, không phải control-flow bug
- Khó debug (lỗi opaque)

## Fix

Cho `shm_size <= mem_limit`, hoặc nâng `mem_limit` lên trên `shm_size`:
```ini
# .env — option A: shm nhỏ hơn mem
CONTAINER_MEM_LIMIT=2g
CONTAINER_SHM_SIZE=1g
# hoặc option B: mem >= shm
CONTAINER_MEM_LIMIT=3g
CONTAINER_SHM_SIZE=2g
```

## Test

```bash
# Crawl trang nặng, theo dõi container exit code
docker events --filter event=die
# ❌ 137 (OOM) báo generic "No result"
```
