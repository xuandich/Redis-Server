# BUG-30: clear_state('queued') logs cumulative count per queue (misleading log)

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

Trong loop per-queue, `deleted_keys` là 1 set tích lũy qua TẤT CẢ queue, nhưng log report `len(deleted_keys)` cho mỗi queue → số liệu cộng dồn sai. Chỉ là log cosmetic; `deleted_count` cuối (line 632) đúng.

### Root Cause

[Dashboard/app.py:604-615](Dashboard/app.py#L604-L615):
```python
deleted_keys = set()           # ← init 1 lần, ngoài loop
for queue_name in queue_names:
    q = Queue(queue_name, connection=redis_conn)
    for jid in q.get_job_ids():
        deleted_keys.add(jid)  # ← tích lũy across queues
    q.empty()
    logger.info(f"Emptied queue {queue_name}: {len(deleted_keys)} jobs")  # ← cộng dồn
```
fnac=3, amazon=2 → log "fnac: 3" rồi "amazon: 5" (5 gồm cả fnac).

## Fix

```python
for queue_name in queue_names:
    q = Queue(queue_name, connection=redis_conn)
    jids = q.get_job_ids()
    deleted_keys.update(jids)
    q.empty()
    logger.info(f"Emptied queue {queue_name}: {len(jids)} jobs")   # số của riêng queue này
```

## Test

```bash
# 2 queue non-empty, POST /api/clear_state/queued, xem log
# ❌ số queue thứ 2 gồm cả queue 1
```
