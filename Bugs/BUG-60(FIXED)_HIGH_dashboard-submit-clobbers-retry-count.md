# BUG-60: Dashboard submit ghi đè job_state làm mất retry_count → vô hiệu cap retry BUG-20

**Severity**: HIGH
**Status**: FIXED (2026-06-26)
**Date**: 2026-06-26

## Problem

`/api/submit-job` tạo `job_state:{ret_key}` bằng `redis_conn.set(...)` với dict **không có `retry_count`**, ghi đè vô điều kiện. BUG-20 (crash-recovery) dựa vào `retry_count` để giới hạn 3 lần retry; `main.py:_set_job_state` cố tình đọc-và-bảo-toàn `retry_count`, nhưng **dashboard submit thì không**. Nếu một job đang trong vòng retry (recovery đã bump lên 2) bị **re-submit cùng `ret_key`**, dashboard reset `retry_count` về 0 → cap `>=3` không bao giờ đạt → job luôn-lỗi bị re-enqueue **vô hạn** qua mỗi lần orchestrator restart.

### Root Cause

[Dashboard/app.py:809-817](../Dashboard/app.py#L809) (trước fix):
```python
job_state_data = {
    'state': 'queued', 'ret_key': ret_key, 'url': url,
    'domain': domain, 'proxy_type': proxy_type,
    'timestamp': _time.time(),   # ← KHÔNG có retry_count
}
redis_conn.set(f'job_state:{ret_key}', json.dumps(job_state_data), ex=86400)
```
Recovery đọc `retry_count = data.get('retry_count', 0)` ([orchestrator.py:174](../redis_server/orchestrator.py#L174)); thiếu field = 0. Cap `>=3` ([orchestrator.py:213](../redis_server/orchestrator.py#L213)) là cơ chế DUY NHẤT biến job crash-lost thành failed vĩnh viễn → reset nó = retry vô hạn.

## Scenario

```
submit ret_X (rc=0) → crash → recovery rc=1 → crash → recovery rc=2
client re-submit ret_X  → dashboard set job_state KHÔNG retry_count → rc về 0
→ crash → recovery rc=1 → ... lặp mãi, không bao giờ chạm cap 3
```

## Impact

- Cap retry của BUG-20 bị vô hiệu cho mọi job được re-submit
- Job luôn-lỗi chiếm slot + spawn container vô hạn → lãng phí tài nguyên, có thể nghẽn queue

## Fix

Mirror logic của `main.py:_set_job_state`: đọc job_state cũ, bảo toàn `retry_count` trước khi ghi.
```python
retry_count = 0
existing_state = redis_conn.get(f'job_state:{ret_key}')
if existing_state:
    try:
        retry_count = json.loads(existing_state).get('retry_count', 0)
    except Exception:
        pass
job_state_data = { ..., 'retry_count': retry_count, ... }
```
Áp dụng tại [Dashboard/app.py:808-827](../Dashboard/app.py#L808). `redis_conn` dùng `decode_responses=True` nên `existing_state` là str → `json.loads` OK.

## Test

```bash
# Giả lập: tạo job_state với retry_count=2 rồi re-submit cùng ret_key
redis-cli set job_state:ret_fnac_test '{"state":"running","retry_count":2,"ret_key":"ret_fnac_test","url":"x","domain":"fnac"}'
python Run_Test/test_api_job.py "https://www.fnac.com/x" fnac   # dùng ret_key=ret_fnac_test
redis-cli get job_state:ret_fnac_test | grep -o '"retry_count":[0-9]*'
# ✅ sau fix: retry_count=2 (giữ nguyên), KHÔNG về 0
```
