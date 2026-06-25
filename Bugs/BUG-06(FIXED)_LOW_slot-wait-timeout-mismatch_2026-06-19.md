# BUG-06: Slot-wait có thể vượt job_timeout

- **Severity:** LOW (phần lớn được throttle che)
- **Status:** FIXED (2026-06-19)
- **File:** `main.py:30-43` (`_acquire_slot` timeout=300), `main.py:77,87`, các client `job_timeout`

## Mô tả

`crawl_job` chờ slot tuần tự:
- `_acquire_slot('global', ...)` — timeout 300s
- `_acquire_slot('domain', ...)` — timeout 300s
- container run — JOB_TIMEOUT (120s)

Worst case ≈ 720s, trong khi `job_timeout` của client:
- `submit_job` (Dashboard): 600s
- `test_job.py`: 180s
- `test_batch.py`: `num_requests * 30`

Nếu job ngồi chờ slot lâu hơn `job_timeout` → death penalty (SIGALRM trong child) giết job →
job kẹt giống BUG-02 (job_state còn, không có result).

## Tại sao LOW

`_can_acquire_slots` ở orchestrator (`orchestrator.py:63`) throttle TRƯỚC khi dequeue → job nằm
chờ trong **queue** (chưa tính job_timeout), không nằm chờ trong `crawl_job`. Chỉ các job
overshoot do race (dequeue trước khi job khác kịp INCR slot) mới phải chờ trong `crawl_job`,
thường rất ngắn (vài giây tới khi 1 slot được nhả).

→ Hiếm khi kích hoạt trong thực tế, nhưng vẫn là một mismatch cấu hình tiềm ẩn.

## Hướng sửa

Giảm `_acquire_slot` timeout xuống giá trị nhỏ hơn nhiều so với `job_timeout` (vd 60-90s) và
fail rõ ràng (ghi result failed) thay vì để job chết âm thầm vì death penalty.

## Liên quan

BUG-02 (job kẹt khi chết giữa chừng).
