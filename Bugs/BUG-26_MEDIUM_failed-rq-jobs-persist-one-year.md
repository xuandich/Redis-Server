# BUG-26: Failed RQ jobs persist for 1 YEAR (failure_ttl default), never cleaned up

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-19

## Problem

Enqueue không set `failure_ttl` → RQ dùng mặc định `DEFAULT_FAILURE_TTL = 31536000` (1 năm). Khi `crawl_job` raise unhandled exception, `rq:job:{ret_key}` hash (chứa full args + URL) và entry trong `rq:failed:crawler:{domain}` registry tồn tại 1 năm. Không ai cleanup → Redis phình dần theo số job từng fail.

### Root Cause

1. Workers tạo với `default_result_ttl=3600` nhưng **không** `failure_ttl` ([orchestrator.py:92-99](orchestrator.py#L92-L99)).

2. Enqueue không truyền `failure_ttl`:
   - [Dashboard/app.py:813-821](Dashboard/app.py#L813-L821) — chỉ `job_timeout, job_id`
   - [orchestrator.py:168-169](orchestrator.py#L168-L169) — chỉ `job_timeout, job_id`

3. RQ `FailedJobRegistry.add` dùng `DEFAULT_FAILURE_TTL = 31536000` (1 năm) khi `failure_ttl=None`.

4. [orchestrator.py:189-211](orchestrator.py#L189-L211) — `cleanup_stale_workers` chỉ xóa `rq:worker:*` + `slots:*`, không bao giờ đụng `rq:job:*`, `rq:finished:*`, `rq:failed:*`.

## Scenario

```
Job fail ở mức RQ (vd BUG-15: containers.run() raise)
  → rq:job:{ret_key} hash + rq:failed:crawler:fnac zset entry
  → TTL = 1 năm
Sau 3600s: result:{ret_key} + job_state hết hạn
Nhưng rq:job:{ret_key} + failed registry còn ~365 ngày
Nhiều job fail → tích lũy không cleanup
```

## Impact

- Redis memory phình theo failure rate (cửa sổ 1 năm)
- Chỉ trigger ở path unhandled-failure (ít gặp) → growth chậm
- Không ảnh hưởng correctness, chỉ resource hygiene

## Fix

Set `failure_ttl` ngắn khi enqueue (cả 2 chỗ):
```python
queue.enqueue('main.crawl_job', ..., job_timeout=600, job_id=ret_key,
              failure_ttl=86400)   # giữ failed 1 ngày thay vì 1 năm
```
Hoặc thêm cleanup `rq:failed:*`/`rq:finished:*` registry vào `cleanup_stale_workers`.

## Test

```bash
# Trigger RQ-level failure
# Inspect Redis
redis-cli -p 6379 KEYS 'rq:job:*'
redis-cli -p 6379 TTL rq:job:{ret_key}
# ❌ hiện tại: ~31536000 (1 năm)
# ✅ sau fix: ~86400
```
