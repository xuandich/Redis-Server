# BUG-23: Orphan worker containers leak + double-spawn on orchestrator crash/stop

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-19

## Problem

Worker containers spawn ngoài docker-compose (`detach=True`, không `name`/label). Không có cơ chế track/cleanup. Khi orchestrator bị kill giữa chừng (hoặc `stop.sh`), worker containers vẫn chạy (1g mem + SYS_ADMIN), restart lại re-enqueue → **spawn container thứ 2 cùng ret_key**, orphan ghi result muộn đè lên run mới.

### Root Cause

1. [main.py:134-153](main.py#L134-L153) — `containers.run(detach=True, remove=True, ...)` không có `name=` cũng không `labels=` → container có tên ngẫu nhiên, không định danh ổn định.

2. [stop.sh:41](stop.sh#L41) và [start.sh:10](start.sh#L10) — chỉ `docker compose stop`, chỉ stop redis/orchestrator/dashboard. Worker containers không thuộc compose project → không bị stop.

3. [orchestrator.py:189-211](orchestrator.py#L189-L211) — `cleanup_stale_workers` chỉ xóa `rq:worker:*` + `slots:*` Redis keys, **không** `containers.list()/kill()` worker-* containers.

4. [orchestrator.py:166-169](orchestrator.py#L166-L169) — `_retry_stale_jobs` re-enqueue cùng `job_id=ret_key` → dequeue lại spawn container thứ 2.

## Scenario

```
3 fnac containers đang crawl
docker kill orchestrator (hoặc OOM)
  → 3 container vẫn chạy (mồ côi)
Restart orchestrator:
  cleanup_stale_workers xóa slots:* (về 0)
  _retry_stale_jobs re-enqueue 3 in-flight jobs
  → spawn 3 container MỚI (load gấp đôi)
  → orphan cũ crawl xong, ghi result:{ret_key} muộn
  → đè lên result của run mới
```

## Impact

- Leak resource (mỗi container tới 1g mem, SYS_ADMIN)
- Double crawl load (gấp đôi)
- Orphan ghi result muộn → clobber run mới
- Self-limiting một phần (remove=True + JOB_TIMEOUT bound) nhưng trong cửa sổ đó vẫn hại

## Fix

1. Gắn label khi spawn để track:
```python
container = docker_client.containers.run(..., labels={'crawler.ret_key': ret_key, 'crawler.domain': domain})
```
2. `cleanup_stale_workers` kill orphan trước khi re-enqueue:
```python
for c in docker_client.containers.list(filters={'label': 'crawler.ret_key'}):
    print(f"[Cleanup] Killing orphan container {c.short_id}")
    try: c.kill()
    except Exception: pass
```
3. `stop.sh` cũng nên kill worker containers (theo label) trước `docker compose stop`.

## Test

```bash
# Submit nhiều jobs → worker containers chạy
docker kill orchestrator
docker ps   # ❌ worker-* vẫn chạy
docker compose up -d orchestrator
# ✅ sau fix: orphan bị kill trước khi re-enqueue, không double-spawn
```
