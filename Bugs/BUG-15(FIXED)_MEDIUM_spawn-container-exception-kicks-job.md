# BUG-15: containers.run() exception doesn't write result, job kicks indefinitely

**Severity**: MEDIUM  
**Status**: OPEN  
**Date**: 2026-06-19

## Problem

`_spawn_and_wait_container` không bọc try quanh `docker_client.containers.run()`. Nếu Docker daemon lỗi (hết RAM, network), `run()` raise exception → không ghi `result:{ret_key}`, không clear `job_state:{ret_key}`. Job **kẹt state `running` vĩnh viễn**, client poll 404, chỉ phục hồi khi restart orchestrator.

### Root Cause

[main.py:134](main.py#L134):
```python
container = docker_client.containers.run(
    image_name,
    ... # 20+ lines config
)  # ← No try/except wrapping this entire block

try:
    container.wait(timeout=JOB_TIMEOUT)  # ← Only wrap wait(), not run()
except Exception as e:
    # Handle wait() error, ghi result
```

Nếu `run()` fail trước `wait()`:
- Exception propagate qua `crawl_job` → RQ job fail
- Nhưng **không execute `finally` block** (bỏ slot release) ← BUG khác
- **Không ghi result** → client poll 404

### Scenario

```
crawl_job() execute:
  _acquire_slot('global') ✓
  _acquire_slot('domain') ✓
  job_state = 'running' ✓
  
  _spawn_and_wait_container():
    docker_client.containers.run() ← Docker daemon out of memory → raise
    
Exception propagate:
  finally: release slots ✓
  finally: do NOT clear job_state (ngoài try)
  
Redis state:
  job_state:{ret_key} = 'running' (không xóa)
  result:{ret_key} = không tồn tại
  
Client:
  GET /api/job/{ret_key} → 404
  GET /api/jobs → thấy job "running" mãi mãi
  Mải chỉ phục hồi khi restart
```

## Impact

- Job kẹt state `running`, lao buộc UI hiển thị sai
- Client không biết job fail hay chạy lâu
- Cứ mỗi lần Docker blip là job kẹt (không phục hồi tự động)
- Chỉ reset khi restart orchestrator (downtime)

## Fix

Bọc try quanh `containers.run()`:
```python
try:
    container = docker_client.containers.run(...)
except Exception as e:
    print(f"[{domain}] Container run failed: {e}")
    error_result = {
        'url': url, 'ret_key': ret_key, 'domain': domain,
        'error': f'Container run failed: {str(e)}', 'status': 'failed',
        'timestamp': time.time(),
    }
    redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
    return error_result

try:
    container.wait(timeout=JOB_TIMEOUT)
    ...
except Exception as e:
    # existing code
```

## Test

```bash
# Stop Docker daemon
sudo systemctl stop docker

# Submit job
python test_api_job.py "https://www.fnac.com/product" "fnac"

# Restart Docker
sudo systemctl start docker

# Check result
curl http://localhost:5000/api/job/{ret_key}
# ✅ Should return error (not 404)

# Dashboard
# ✅ Job should show "failed" (not stuck "running")
```
