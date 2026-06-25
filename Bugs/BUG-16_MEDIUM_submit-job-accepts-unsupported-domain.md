# BUG-16: submit-job accepts domain without worker, job stuck queued

**Severity**: MEDIUM  
**Status**: OPEN  
**Date**: 2026-06-19

## Problem

`/api/submit-job` chấp nhận URL từ domain không có worker. Job enqueue vào queue `crawler:{domain}` nhưng không ai consume nó → **job stuck queued 24h** nhưng API vẫn trả **202 success**. Client nhận success response không biết rằng job sẽ không bao giờ execute.

### Root Cause

[Dashboard/app.py:729-743](Dashboard/app.py#L729-L743) — `_extract_domain_from_url()` fallback:
```python
# Extract domain name: fnac.com -> fnac, amazon.fr -> amazon
if 'fnac' in domain:
    return 'fnac'
elif 'amazon' in domain:
    return 'amazon'
else:
    # Return base domain if no match — đây là lỗi
    return domain.split('.')[0]

# https://www.abc.com → domain='www.abc.com' → 'www'
# Queue: crawler:www (không ai listen)
```

**Không validate** rằng domain này có worker đang chạy. Orchestrator chỉ discover worker từ `workers/` folder (có Dockerfile), nhưng submit-job không check.

### Scenario

```
Client POST /api/submit-job
  URL: https://www.unknown.com/product
  Domain extracted: 'unknown'
  Queue: crawler:unknown (không có worker)
  
API response: 202 {status: 'queued', ...}
  ← Client nhận success

Redis:
  rq:queue:crawler:unknown = [job1, job2, ...] (idle, no consumer)
  job_state:unknown:* = 'queued'

Dashboard:
  Queued count tăng, nhưng job không bao giờ move to running
  
Client poll:
  Vẫn thấy job "queued" sau 1h, 10h, 24h
```

## Impact

- Client không biết job fail hay chạy
- Lãng phí resources (job kẹt Redis 24h)
- Confusion — API nói success nhưng không xảy ra gì
- Dashboard bị contaminate với phantom jobs

## Fix

Validate domain trước enqueue — chỉ enqueue nếu worker đã discover:
```python
# In orchestrator hoặc config
AVAILABLE_DOMAINS = {'fnac', 'amazon'}  # hoặc discover từ workers/

# In submit-job:
domain = _extract_domain_from_url(url)
if domain not in AVAILABLE_DOMAINS:
    return jsonify({'error': f'Domain {domain} not supported. Available: {AVAILABLE_DOMAINS}'}), 400
```

Hoặc orchestrator expose `/api/domains` endpoint, submit-job check trước.

## Test

```bash
# Submit job từ domain không hỗ trợ
curl -X POST http://localhost:5000/api/submit-job \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.example.com/page","ret_key":"test-uuid","proxy_type":"standard"}'

# ✅ Should return 400 (not 202)
# ❌ Current: returns 202, job stuck queued
```
