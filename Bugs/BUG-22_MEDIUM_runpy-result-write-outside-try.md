# BUG-22: run.py result write (r.setex) is outside try/except

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-19

## Problem

Chỗ duy nhất `run.py` ghi `result:{ret_key}` là line 44, **NGOÀI** try/except (try kết thúc line 41). Nếu `process_single_request` thành công nhưng `r.setex` cuối cùng raise (Redis blip, connection reset, OOM-killed giữa write), exception propagate, container exit non-zero, **không result nào được ghi**. Kết quả crawl thành công bị mất âm thầm.

### Root Cause

[workers/fnac/run.py:24-45](workers/fnac/run.py#L24-L45):
```python
try:
    request = {...}
    result = await process_single_request(request, asyncio.Semaphore(1))
except Exception as e:
    result = {... 'status': 'failed' ...}   # ← try kết thúc line 41
    print(f"[FNAC] Exception: {e}")

print(f"[FNAC] status=...")
r.setex(f"result:{ret_key}", result_ttl, json.dumps(result, ...))  # ← line 44, NGOÀI try
```

Cũng vậy: `redis.Redis(...)` (line 22) và `int(os.environ.get('REDIS_PORT'))` (line 19) đều ngoài try.

Kết hợp với BUG-21 (`container.wait()` không raise trên exit≠0), main.py đọc None → ghi generic "No result from container", **đè** result thành công lẽ ra đã có.

## Scenario

```
process_single_request trả result tốt
Redis connection drop đúng lúc r.setex (line 44)
  → unhandled exception, container exit non-zero
  → main.py container.wait() không raise (BUG-21), đọc None
  → ghi 'No result from container', status failed
Client nhận failed cho job đã crawl thành công
```

## Impact

- Mất data: result thành công → báo failed
- Window hẹp (Redis phải fail đúng lúc setex cuối) nhưng có thật

## Fix

Bọc result write trong try + retry:
```python
for attempt in range(3):
    try:
        r.setex(f"result:{ret_key}", result_ttl, json.dumps(result, ensure_ascii=False, default=str))
        break
    except Exception as e:
        print(f"[FNAC] result write failed (attempt {attempt+1}): {e}")
        await asyncio.sleep(1)
```

## Test

```bash
# Submit job, kill/restart Redis đúng lúc worker sắp ghi result (khó canh — dùng toxiproxy/iptables)
# ✅ result phải được ghi sau retry (không mất)
```
