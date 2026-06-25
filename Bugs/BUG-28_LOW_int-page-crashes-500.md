# BUG-28: int(page) crashes with HTTP 500 on non-numeric ?page=, negative slice on page<=0

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`page` parse bằng `int(request.args.get('page', 1))` **ngoài** try/except. `?page=abc` raise `ValueError` → 500. `page=0`/âm → `start=(page-1)*per_page < 0` → slice index âm trả data sai/rỗng thay vì lỗi 400.

### Root Cause

[Dashboard/app.py:78](Dashboard/app.py#L78):
```python
page = int(request.args.get('page', 1))   # ← line 78, NGOÀI try
per_page = 20
all_jobs = []
try:                                        # ← try bắt đầu line 82
```
`int('abc')` raise trước line 82 → `except Exception` (line 202) không catch → global 500 handler. `page=0` → `start=-20, end=0` → `all_jobs[-20:0]` (rỗng); `page=-1` → `all_jobs[-40:-20]` (data sai).

## Fix

```python
try:
    page = max(1, int(request.args.get('page', 1)))
except (ValueError, TypeError):
    return jsonify({'error': 'Invalid page'}), 400
```

## Test

```bash
curl -s -o /dev/null -w "%{http_code}" "http://localhost:5000/api/jobs/finished?page=abc"
# ❌ 500  →  ✅ 400
```
