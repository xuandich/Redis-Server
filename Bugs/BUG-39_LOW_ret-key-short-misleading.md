# BUG-39: ret_key_short trả 8 ký tự đầu của full key — luôn là 'ret_newa' / 'ret_fnac'

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-22

## Problem

`submit_job` (app.py) trả `ret_key_short = ret_key[:8]`. Với format `ret_{domain}_{uuid}`, 8 ký tự đầu luôn là prefix domain chứ không phải identifier của job. Ví dụ: mọi newark job đều trả `'ret_newa'`, mọi fnac job đều trả `'ret_fnac'` — không phân biệt được job nào với job nào.

### Root Cause

[Dashboard/app.py:828](Dashboard/app.py#L828):
```python
'ret_key_short': ret_key[:8],
```

Với `ret_key = 'ret_newark_550e8400-e29b-41d4-a716-446655440000'`:
- `ret_key[:8]` = `'ret_newa'` — prefix domain, trùng nhau cho mọi newark job

Tương tự trong `/api/jobs` (app.py:257, 295, 344):
```python
'ret_key': ret_key[:8],
```

### Scenario

```
10 newark jobs submit → dashboard hiển thị 10 dòng ret_key = 'ret_newa'
Không phân biệt được job nào với job nào từ short key
```

## Impact

- Dashboard/logging không nhận dạng được individual job từ short key
- Confusing nhưng không ảnh hưởng functional (full `ret_key_full` vẫn đúng)
- Low: chỉ ảnh hưởng display

## Fix

Lấy phần UUID thay vì prefix:
```python
# Lấy phần sau 'ret_{domain}_'
parts = ret_key.split('_', 2)
short = parts[2][:8] if len(parts) >= 3 else ret_key[:8]
'ret_key_short': short,
```

Kết quả: `'550e8400'` thay vì `'ret_newa'` — unique per job.

## Test

```bash
python -c "
import requests, uuid
ret_key = f'ret_newark_{uuid.uuid4()}'
r = requests.post('http://localhost:5000/api/submit-job', json={'url':'https://www.newark.com/x','mode':'none','proxy_type':'none','ret_key':ret_key})
print(r.json()['ret_key_short'])
# ❌ 'ret_newa'  →  ✅ xxxxxxxx (UUID prefix)
"
```
