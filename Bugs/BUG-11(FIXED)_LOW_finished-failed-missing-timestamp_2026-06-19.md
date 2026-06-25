# BUG-11: Finished/failed jobs thiếu `timestamp` — sort không hoạt động

- **Severity:** LOW
- **Status:** FIXED (2026-06-19)
- **File:** `Dashboard/app.py:254` (`get_jobs`), `Dashboard/app.py:173` (`get_jobs_by_state`)

## Mô tả

Sau fix BUG-08, dashboard sort tất cả jobs theo `x.get('timestamp', 0)` (newest first).
Tuy nhiên `job_info` cho finished/failed được build từ `result:*` keys và **không có field
`timestamp`**:

```python
# get_jobs() line 254 — finished/failed
job_info = {
    'ret_key': ret_key[:8],
    'ret_key_full': ret_key,
    'url': result.get('url', 'N/A'),
    'domain': result.get('domain', 'unknown'),
    'status': result.get('status', 'unknown'),
    'http_code': result.get('http_code', 0),
    'error': result.get('error', ''),
    'html_size': len(result.get('html', '')),
    'total_elapsed_seconds': result.get('total_elapsed_seconds', 0),
    # ← không có 'timestamp'
}
```

```python
# get_jobs_by_state() line 173 — finished/failed
all_jobs.append({
    'ret_key': ret_key,
    'url': result.get('url', 'N/A'),
    'domain': result.get('domain', 'unknown'),
    'status': job_status,
    'http_code': result.get('http_code', 0),
    # ← không có 'timestamp'
})
```

`x.get('timestamp', 0)` fallback về 0 → tất cả finished/failed đều bằng nhau → thứ tự
hiển thị là undefined (không crash nhưng sort không có ý nghĩa).

## Hậu quả

Dashboard tab Finished và Failed không sort theo thời gian. Gây khó theo dõi khi có
nhiều job.

## Hướng sửa

Hai lựa chọn:

**A. Đọc timestamp từ `result:*` nếu worker ghi vào** (tốt nhất):
```python
'timestamp': result.get('finished_at') or result.get('timestamp', 0),
```

**B. Fallback sang RESULT_TTL để xấp xỉ thời gian** (không chính xác):
Không khả thi vì TTL còn lại không ánh xạ ngược ra thời gian tạo.

**C. Thêm `timestamp: time.time()` vào result trong `_spawn_and_wait_container`** (chắc chắn):
```python
# _spawn_and_wait_container — trước khi return
if result:
    result_dict = json.loads(result)
    result_dict.setdefault('timestamp', time.time())
    return result_dict
```
Thêm `timestamp` vào tất cả result paths (success, timeout error, no-result error).

## Liên quan

BUG-08 (sort theo UUID → timestamp).
