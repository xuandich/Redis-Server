# BUG-43: Dashboard drop toàn bộ failed/finished jobs vì `html: null` → `len(None)` TypeError

**Severity**: HIGH
**Status**: FIXED
**Date**: 2026-06-22

## Problem

`/api/jobs` luôn trả về `finished=0, failed=0` dù Redis có đủ `result:*` keys với status='failed'.

## Root Cause

[Dashboard/app.py:264](Dashboard/app.py#L264):
```python
'html_size': len(result.get('html', '')),
```

Khi container worker ghi kết quả với `"html": null` (ví dụ: trang lỗi, timeout, no proxy), `result.get('html', '')` trả về `None` — không phải `''` — vì key `html` **tồn tại** trong dict, chỉ là value là `null`/`None`. Default `''` chỉ dùng khi key **không tồn tại**.

Sau đó `len(None)` → `TypeError: object of type 'NoneType' has no len()` → bị catch bởi `except: pass` → job bị skip hoàn toàn.

`seen_result` vẫn tăng (add trước khi parse), nên log hiển thị `result=10` nhưng `Failed=0`.

## Scenario

```
Worker container runs → result: {"html": null, "status": "failed", "error": "No proxy available", ...}
Dashboard scans result:* → finds 10 keys
For each key:
  seen_result.add(ret_key)  ← counted here (result=10 in log)
  ...
  'html_size': len(result.get('html', ''))  → len(None) → TypeError
  except: pass  ← silently dropped
→ finished=0, failed=0
```

## Impact

- **HIGH**: Dashboard hoàn toàn mù với tất cả failed jobs khi html=null
- Không thể debug lỗi qua dashboard
- Tất cả requests trả về 0 failed, trông như jobs biến mất sau running

## Fix

```python
# Trước:
'html_size': len(result.get('html', '')),

# Sau:
html = result.get('html') or ''
'html_size': len(html),
```

`or ''` xử lý cả `None` (html=null) lẫn key không tồn tại.

## Affected Code

- [Dashboard/app.py:264](Dashboard/app.py#L264) — trong `get_jobs()` function
- Cũng check [Dashboard/app.py:183](Dashboard/app.py#L183) — trong `get_jobs_by_state()`, cùng pattern

## Test

```bash
# Verify bug:
docker exec redis-server redis-cli GET "result:ret_newark_..." | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
print('html value:', repr(d.get('html', '')))  # None, not ''
print('len:', len(d.get('html', '')))           # TypeError
"

# Verify fix:
curl http://localhost:5000/api/jobs | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('failed:', len(d['failed']), 'finished:', len(d['finished']))
"
```
