# BUG-29: Queued-from-RQ URL always 'N/A' — bytes key lookup with decode_responses=True

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`redis_conn` tạo với `decode_responses=True` → `hgetall` trả dict key/value là `str`. Nhưng line 141 lookup `job_hash.get(b'description', ...)` bằng **bytes key** → không bao giờ match str key `'description'` → fallback `b''` → `.decode()` = `''` → regex không match → `url` luôn `'N/A'` cho mọi queued job từ RQ queue trong `/api/jobs/<state>`.

### Root Cause

[Dashboard/app.py:45](Dashboard/app.py#L45) — `Redis(..., decode_responses=True)`.

[Dashboard/app.py:141](Dashboard/app.py#L141):
```python
description = job_hash.get(b'description', b'').decode() if isinstance(job_hash.get(b'description', b''), bytes) else job_hash.get('description', '')
```
`job_hash.get(b'description', b'')` (bytes key) → default `b''` → `isinstance(b'', bytes)` True → `b''.decode()` = `''`. Nhánh else (str key đúng) không bao giờ chạy.

Đối chiếu: `/api/jobs` ở [app.py:338](Dashboard/app.py#L338) dùng đúng str key `'description'` → 2 endpoint báo URL khác nhau cho cùng job.

## Fix

```python
description = job_hash.get('description', '')   # decode_responses=True → str key
```

## Test

```bash
# Submit job, trước khi dequeue:
curl http://localhost:5000/api/jobs/queued
# ❌ url: 'N/A'  →  ✅ url thật
```
