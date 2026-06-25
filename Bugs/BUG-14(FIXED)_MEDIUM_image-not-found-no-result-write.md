# BUG-14: Image not found path doesn't write result:{ret_key}

**Severity**: MEDIUM  
**Status**: OPEN  
**Date**: 2026-06-19

## Problem

Khi worker image bị missing, `_spawn_and_wait_container` return error dict nhưng **không ghi `result:{ret_key}` vào Redis**. Trong khi các error path khác (timeout, no-result) đều ghi. Hậu quả: client poll `/api/job/{ret_key}` nhận 404 mãi mãi.

### Root Cause

[main.py:124-125](main.py#L124-L125):
```python
error_msg = f'Worker image {image_name} not found'
return {'url': url, 'ret_key': ret_key, 'domain': domain, 'error': error_msg, 'status': 'failed'}
# ← Return dict, nhưng KHÔNG setex result:{ret_key}
```

Điều này **không nhất quán** với:
- **Line 168** (timeout/error path): `redis_client.setex(f"result:{ret_key}", ...)`
- **Line 182** (no-result path): `redis_client.setex(f"result:{ret_key}", ...)`

### Scenario

```
Client gửi job → Container image missing
  crawl_job xác định image missing → return error dict
  main() nhận error dict, không ghi result
Client poll: GET /api/job/{ret_key}
  → Redis không có result:{ret_key}
  → Response: 404 Not Found (mãi mãi)
User không biết job fail hay đang chạy
```

## Impact

- Client poll không có kết quả, bị hang (TTL job_state 24h)
- Client không biết job fail vì sao
- Inconsistent error handling — một số path ghi, một số không

## Fix

Thêm `setex` cho image not found path (line 125 sau return):
```python
if os.path.exists(cache_file):
    ...
else:
    error_msg = f'Worker image {image_name} not found'
    error_result = {'url': url, 'ret_key': ret_key, 'domain': domain, 'error': error_msg, 'status': 'failed'}
    redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(error_result, ensure_ascii=False, default=str))
    return error_result
```

## Test

```bash
# Stop worker fnac image
docker rmi worker-fnac:latest

# Submit job
python test_api_job.py "https://www.fnac.com/product" "fnac"

# Poll result
curl http://localhost:5000/api/job/{ret_key}
# ✅ Should return error with status=failed (not 404)
```
