# BUG-08: Dashboard sort theo UUID, không theo thời gian

- **Severity:** LOW
- **Status:** FIXED (2026-06-19)
- **File:** `Dashboard/app.py:356-358`

## Mô tả

```python
# Sort by ret_key (most recent last)
for status in ['queued', 'running', 'finished', 'failed']:
    jobs_data[status].sort(key=lambda x: x['ret_key_full'], reverse=True)
```

`ret_key` là UUID v4 (ngẫu nhiên — `uuid.uuid4()` trong client). Sort theo UUID **không** phản
ánh thứ tự thời gian, dù comment ghi "most recent last".

## Hậu quả

Danh sách job trên dashboard hiển thị thứ tự ngẫu nhiên, không phải mới nhất trước/sau. Gây
khó theo dõi. Thuần UI, không ảnh hưởng xử lý job.

## Hướng sửa

Sort theo `timestamp` (đã có sẵn trong `job_state`) cho queued/running. Với finished/failed,
result hiện không lưu thời điểm hoàn thành — cân nhắc thêm field `finished_at` vào result rồi
sort theo đó.
