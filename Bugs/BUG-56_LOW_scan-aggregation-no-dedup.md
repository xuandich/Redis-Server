# BUG-56: SCAN aggregation thiếu dedup trong get_stats/get_jobs_by_state/clear_*, thổi phồng số liệu khi Redis rehash

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-23

## Problem

Redis `SCAN` có thể trả về cùng một key nhiều lần qua các vòng cursor khi keyspace đang rehash (tài liệu Redis nói rõ SCAN không đảm bảo tính duy nhất). `get_jobs` đã phòng việc này bằng set `seen_result`, nhưng `get_jobs_by_state` (nhánh finished/failed), `get_stats`, `queue_stats_compat` và các endpoint `clear_*` thì **không** dedup. Điều này khiến cùng một `result:{ret_key}` bị append/đếm nhiều hơn một lần.

## Root Cause

Trong [app.py](Dashboard/app.py#L158-L188), nhánh finished/failed không có set `seen`:

```python
while True:
    cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
    for key in keys:
        ...
        all_jobs.append({...})   # không kiểm tra trùng
    if cursor == 0:
        break
```

Tương tự `get_stats` ([app.py](Dashboard/app.py#L386-L408)) cộng `total_keys += 1` cho mỗi key mà không có set `seen`. Đối chiếu `get_jobs` ([app.py](Dashboard/app.py#L247-L249)) đã có ghi chú và phòng vệ:

```python
if ret_key in seen_result:
    continue  # SCAN trả duplicate khi Redis rehash
seen_result.add(ret_key)
```

## Scenario

Khi keyspace `result:*` đang tăng nhanh và Redis rehash dict nội bộ, một lần gọi `/api/stats` hoặc `/api/jobs_by_state?state=finished` rơi đúng vào lúc rehash → cùng một result xuất hiện nhiều lần trong list phân trang và `total`/`success_rate` bị thổi phồng (có thể vượt 100%).

## Impact

Gián đoạn, phụ thuộc tải: đúng vào lúc lưu lượng cao (khi metric quan trọng nhất), dashboard hiển thị dòng trùng và success_rate sai lệch. Chỉ đọc, không hỏng dữ liệu, nhưng làm metric mà operator dựa vào trở nên không đáng tin.

## Fix

Thêm set `seen` theo từng request (key theo `ret_key` hoặc raw key) trong `get_jobs_by_state` finished/failed, `get_stats` và `queue_stats_compat`, mô phỏng `seen_result` của `get_jobs`:

```python
seen = set()
while True:
    cursor, keys = redis_conn.scan(cursor, match='result:*', count=100)
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        ...
```

## Related

Liên quan jobs-by-state-unsorted-pagination và clear-state-cumulative-log-count đã ghi nhận, nhưng đây là lỗi thiếu dedup SCAN riêng biệt ở nhiều endpoint.
