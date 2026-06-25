# BUG-19: Container wait() race with exit/remove overwrites good result

**Severity**: LOW  
**Status**: OPEN  
**Date**: 2026-06-19

## Problem

Nếu container exit và bị remove **giữa `run()` return và `wait()` call**, `wait()` sẽ fail → except block ghi error result **đè lên** kết quả tốt mà worker vừa ghi. Hiếm nhưng có thể xảy ra với container fast-exit hoặc Docker daemon slow.

### Root Cause

[main.py:154-169](main.py#L154-L169) — `remove=True` flag:
```python
container = docker_client.containers.run(
    ...,
    remove=True,  # ← Remove container khi exit
    ...
)

try:
    container.wait(timeout=JOB_TIMEOUT)  # ← If container already exited, may fail
    print(f"[{domain}] Container {container.short_id} finished")
except Exception as e:
    # ...
    error_result = {
        'error': f'Container timeout/error: {str(e)}', ...
    }
    redis_client.setex(f"result:{ret_key}", ...)  # ← OVERWRITE good result
    return error_result
```

Race window:
1. Container spawned, start executing
2. Container finish + write result → `redis:result:{ret_key}`
3. Container auto-remove (exit code 0)
4. Worker call `container.wait()` → container không tồn tại → exception
5. Except block ghi error result → **overwrite** kết quả tốt

### Scenario

```
Worker Dockerfile:
  RUN main.py  # Xử lý, write result:{ret_key} ✓
  
Docker:
  1. main.py xong, write result tốt
  2. exit code 0
  3. auto-remove=True → delete container
  4. (Milliseconds overlap)
  
Orchestrator:
  container.wait() → container không tồn tại
  → raise DockerError("Container not found")
  → except: overwrite result với error message
  
Redis:
  result:{ret_key} = error (đè lên good result)

Client:
  nhận error response thay vì success
```

### Impact

- **Job success nhưng client nhận error** — logic fail
- Dữ liệu mất (good result overwrite)
- Hiếm lắm (phải container exit + remove trong milliseconds)
- Single-domain / bình thường không gặp

### Fix

Check container existence trước ghi error:
```python
try:
    container.wait(timeout=JOB_TIMEOUT)
except Exception as e:
    # Container may have exited already and been auto-removed
    # Check if result was already written by worker
    existing_result = redis_client.get(f"result:{ret_key}")
    if existing_result:
        # Worker wrote result before container removed — use it
        return json.loads(existing_result)
    
    # No result written, container failed
    error_result = {...}
    redis_client.setex(f"result:{ret_key}", ...)
    return error_result
```

Hoặc remove=False, manual cleanup:
```python
container = docker_client.containers.run(
    ...,
    remove=False,  # ← Manual cleanup
)
try:
    container.wait(...)
finally:
    try:
        container.remove(force=True)
    except:
        pass
```

## Test

```bash
# Worker Dockerfile: add short-lived container
# E.g., container xong trong 0.5s, Docker remove trong 0.1s

# Submit rapid job
python test_api_job.py "https://www.fnac.com/..." "fnac"

# Monitor result
curl http://localhost:5000/api/job/{ret_key}

# ✅ Should return success (not error)
# ❌ Currently may overwrite with error
```

**Note**: Bug này rất hiếm vì:
1. Cần container exit đúng lúc
2. Cần Docker daemon remove nhanh
3. Cần orchestrator gọi wait() đúng window
4. Test labs unlikely to trigger
