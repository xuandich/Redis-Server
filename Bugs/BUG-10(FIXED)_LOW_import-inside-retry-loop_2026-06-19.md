# BUG-10: Import module bên trong vòng lặp `_retry_stale_jobs`

- **Severity:** LOW
- **Status:** FIXED (2026-06-19)
- **File:** `orchestrator.py:165`

## Mô tả

Ba import được đặt bên trong vòng lặp xử lý từng `job_state` key:

```python
while True:
    cursor, keys = redis_client.scan(...)
    for key in keys:
        ...
        redis_client.delete(key)
        import main as crawler_main           # ← lặp mỗi iteration
        q = Queue(...)
        q.enqueue(crawler_main.crawl_job, ...)
        import json as _json, time as _time   # ← lặp mỗi iteration
        redis_client.setex(...)
```

## Hậu quả

Python cache module sau lần import đầu (`sys.modules`), nên không crash và không tốn
chi phí load file thêm lần nữa. Tuy nhiên:

- Mỗi iteration vẫn tốn 1 dict lookup vào `sys.modules` + attribute bind → overhead nhỏ
  nhân với số job cần retry
- Code khó đọc: import nằm giữa logic nghiệp vụ, không thể nhìn đầu file để biết
  module phụ thuộc
- `json` và `time` đã được import ở nhiều nơi khác trong hệ thống, import alias trong
  hàm là không cần thiết

## Hướng sửa

Move import lên đầu hàm `_retry_stale_jobs` (hoặc module level):

```python
def _retry_stale_jobs():
    import json
    import time
    from rq.job import Job as RQJob
    from rq.exceptions import NoSuchJobError
    import main as crawler_main
    ...
```

`main` import ở function-level là hợp lý (tránh circular import khi file khởi động),
nhưng nên ở đầu hàm, không trong loop.
