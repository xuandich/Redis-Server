# BUG-21: container.wait() StatusCode ignored — non-zero exit treated as success

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`container.wait()` trả về dict `{'StatusCode': N, 'Error': ...}` và **không raise** khi container exit code ≠ 0. Code bỏ qua return value, chỉ print "Container finished". Container crash (exit 137 OOM, run.py raise) bị coi như chạy bình thường → fall through, đọc result = None → báo generic "No result from container". Lỗi thật (exit code/Error) bị vứt.

### Root Cause

[main.py:155-156](main.py#L155-L156):
```python
container.wait(timeout=JOB_TIMEOUT)   # ← return value bị bỏ
print(f"[{domain}] Container {container.short_id} finished")
```

`docker-py` `container.wait()` chỉ raise khi timeout/connection error (đã catch ở line 157). Non-zero exit code KHÔNG raise — nó nằm trong `StatusCode` của dict trả về, không bao giờ được kiểm tra.

## Scenario

```
Worker container run.py raise trước khi ghi result (vd Redis blip lúc r.setex)
  → container exit code 1
  → container.wait() trả {'StatusCode': 1}, KHÔNG raise
  → code coi như "finished", print success
  → line 171: redis_client.get(result) = None
  → line 177-182: ghi generic {'error': 'No result from container'}
Lỗi thật (exit 1, traceback) không được surface
```

## Impact

- Mất chẩn đoán: lỗi thật bị che bằng "No result from container"
- OOM (exit 137) không phân biệt được với worker logic error
- Khó debug production

## Fix

```python
status = container.wait(timeout=JOB_TIMEOUT)
exit_code = status.get('StatusCode', -1) if isinstance(status, dict) else status
if exit_code != 0:
    print(f"[{domain}] Container exited non-zero: {exit_code}, Error={status.get('Error')}")
    # vẫn đọc result nếu có; nếu không, ghi error_result kèm exit_code
```

## Test

```bash
# Làm run.py exit non-zero trước khi ghi result
# Submit job, check log + result
curl http://localhost:5000/api/job/{ret_key}
# ✅ error message nên chứa exit code thật, không phải generic "No result"
```
