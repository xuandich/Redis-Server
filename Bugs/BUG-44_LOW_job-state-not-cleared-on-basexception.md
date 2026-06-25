# BUG-44: `_clear_job_state` không nằm trong `finally` — job stuck 'running' 24h khi SIGKILL

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-22

## Problem

Khi orchestrator bị kill không sạch (`SIGKILL`, `docker kill -s KILL`, OOM killer), `job_state:{ret_key}` vẫn ở trạng thái `'running'` cho đến hết TTL (24h). Dashboard hiển thị job stuck ở running mãi.

## Root Cause

[main.py:96-113](main.py#L96):
```python
try:
    result = _spawn_and_wait_container(...)
    _clear_job_state(ret_key)      # ← chỉ khi success
    return result
except Exception as e:
    ...
    _clear_job_state(ret_key)      # ← chỉ khi Exception
    raise
finally:
    _release_slot('domain', domain)  # ← slot ĐƯỢC release
```

`_clear_job_state` chỉ có trong `try` và `except Exception`, không có trong `finally`. Trong khi `_release_slot` đúng là nằm trong `finally` → slot được giải phóng, nhưng `job_state` không được xóa.

## Scenario

```
Job đang running, spawned container đang chạy
Process bị SIGKILL (OOM killer, docker stop timeout, operator kill -9)
→ finally: _release_slot('domain') chạy?  Không chắc — SIGKILL không cho phép finally chạy
→ job_state:{ret_key} = 'running' với TTL=86400 (24h)
→ Dashboard shows job stuck in running for 24h
→ Nếu _retry_stale_jobs chạy lúc restart: job được re-enqueue (hành vi đúng)
   nhưng nếu container vẫn đang chạy → 2 containers cho cùng 1 ret_key (BUG-23 liên quan)
```

## Giảm nhẹ

- SIGTERM (graceful shutdown): `finally` chạy được → slot released
- `KeyboardInterrupt` / `SystemExit` không phải `Exception` nhưng `finally` vẫn chạy → slot released, nhưng `job_state` vẫn không cleared
- RQ 2.9.1: `JobTimeoutException` là `Exception` subclass → `except Exception` bắt được → `_clear_job_state` ĐƯỢC gọi khi job timeout
- `_retry_stale_jobs` lúc restart xử lý đúng stale 'running' jobs

## Impact

- LOW: chỉ xảy ra khi SIGKILL hoặc process crash — không phải graceful shutdown
- Dashboard hiển thị sai running count tối đa 24h sau crash

## Fix

```python
try:
    result = _spawn_and_wait_container(url, domain, ret_key, proxy_type)
    print(f"[CRAWL_JOB] {domain} {job_id} - CONTAINER DONE", flush=True)
    return result
except Exception as e:
    print(f"[CRAWL_JOB] {domain} {job_id} - EXCEPTION: {e}", flush=True)
    error_result = {
        'status': 'failed', 'error': str(e),
        'ret_key': ret_key, 'domain': domain, 'url': url,
    }
    redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ...))
    raise
finally:
    _clear_job_state(ret_key)      # ← chuyển vào finally
    _release_slot('domain', domain)
```

## Related

- [[BUG-23]] orphan containers khi orchestrator crash
- [[BUG-03]] slot leak (đã fix)
