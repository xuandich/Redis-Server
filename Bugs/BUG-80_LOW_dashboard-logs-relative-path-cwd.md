# BUG-80: Dashboard tạo/ghi log qua path tương đối 'logs' theo CWD (fragile import-time)

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-27

## Problem

Lúc import module, [Dashboard/app.py:20-24](../Dashboard/app.py#L20):
```python
if not os.path.exists('logs'): os.makedirs('logs')
... RotatingFileHandler('logs/dashboard.log', ...)
```
Cả hai dùng path **tương đối theo CWD**, không neo `__file__`/abspath. Chạy đúng chỉ vì Dockerfile `WORKDIR /app` + `RUN mkdir -p logs` + `CMD ["python","app.py"]` (CWD=/app, /app/logs có sẵn).

## Impact (LOW)

- `python Dashboard/app.py` từ repo root (debug local) → tạo `<repo>/logs` thay vì `Dashboard/logs` (stray dir, cosmetic).
- CWD read-only/khác → `os.makedirs('logs')` raise PermissionError **lúc import** → Flask app crash khởi động.
- LOW: trong container `/app/logs` đã tồn tại nên `makedirs` bị skip; compose không set `read_only`; lỗi (nếu có) lộ ngay lúc start chứ không âm thầm. Cùng lớp path-cwd với BUG-59 nhưng khác code site (không trùng bug nào).

## Fix

Neo vào `__file__`:
```python
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
RotatingFileHandler(os.path.join(LOG_DIR, 'dashboard.log'), ...)
```
