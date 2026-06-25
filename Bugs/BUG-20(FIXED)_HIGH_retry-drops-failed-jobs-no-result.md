# BUG-20: Crash recovery silently DROPS RQ-'failed' jobs that have no result

**Severity**: HIGH
**Status**: FIXED
**Date**: 2026-06-19
**Related**: complement of BUG-15

## Problem

`_retry_stale_jobs` coi job RQ status `failed` là "đã xong" → xóa `job_state` và skip, **không re-enqueue**. Nhưng một `crawl_job` raise exception (BUG-15: `containers.run()` lỗi, hoặc TimerDeathPenalty timeout, OOM) bị RQ đánh dấu `failed` **mà KHÔNG ghi `result:{ret_key}`**. Recovery xóa dấu vết cuối cùng của job → job mất vĩnh viễn.

### Root Cause

[orchestrator.py:154-157](orchestrator.py#L154-L157):
```python
elif job_status in ('finished', 'failed'):
    redis_client.delete(key)   # ← xóa job_state
    skipped += 1
    continue                    # ← KHÔNG re-enqueue
```

Recovery giả định sai: `failed` ⟹ result đã được ghi. Thực tế `crawl_job` (main.py:70-107) chỉ dùng `try/finally` **không có `except`**, nên bất kỳ exception nào từ `_spawn_and_wait_container` propagate ra ngoài → `_clear_job_state` (line 99) không chạy → job_state kẹt `running`, **không có result**, RQ mark `failed`.

## Scenario

```
Submit job → crawl_job → containers.run() raise (docker daemon hiccup)
  → exception propagate, KHÔNG ghi result, job_state vẫn 'running'
  → RQ mark job 'failed'
Restart orchestrator:
  _retry_stale_jobs: job_state 'running', result missing, RQJob status 'failed'
  → delete job_state, skip
Client poll result:{ret_key} → 404 mãi mãi
Job KHÔNG bao giờ được retry
```

## Impact

- **Mất job vĩnh viễn** — đúng thứ mà crash-recovery sinh ra để ngăn
- Không result (client 404), không state, không trong queue
- Bất kỳ unhandled failure nào trong job body cũng trigger (không chỉ BUG-15)

## Fix

Khi RQ status `failed` mà **không có result** → re-enqueue (giống path running):
```python
elif job_status == 'finished':
    redis_client.delete(key)
    skipped += 1
    continue
elif job_status == 'failed':
    # failed nhưng không có result (đã check exists ở trên) → job thật sự lost, re-enqueue
    try:
        rq_job.delete()
    except Exception:
        pass
    # fall through to re-enqueue (không continue)
```

Lưu ý: nên giới hạn số lần retry (tránh loop vô hạn nếu job luôn fail) — thêm retry counter vào job_state.

## Test

```bash
# Trigger crawl_job exception (stop docker daemon mid-job, hoặc bind mount sai)
python test_api_job.py "https://www.fnac.com/x" "fnac"
# Job RQ-failed, không result
docker compose restart orchestrator
# ✅ Job phải được re-enqueue + cuối cùng có result
# ❌ Hiện tại: job bị xóa, client 404 vĩnh viễn
```
