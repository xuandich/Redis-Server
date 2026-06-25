# BUG-09: `clear_state('queued')` đếm gấp đôi số job xóa

- **Severity:** LOW
- **Status:** FIXED (2026-06-19)
- **File:** `Dashboard/app.py:601-627`

## Mô tả

Khi clear state `queued`, code xóa từ **2 nguồn** và cộng dồn `deleted_count`:

1. RQ queue (`q.empty()` — đếm `len(q.get_job_ids())`)
2. `job_state:*` keys có `state == 'queued'`

Một job queued thường tồn tại ở **cả hai** nguồn cùng lúc (RQ job hash + job_state key) →
bị đếm 2 lần.

## Hậu quả

API trả về `deleted` lớn hơn số job thực tế (có thể gấp đôi). Thuần báo cáo sai số, không ảnh
hưởng dữ liệu (việc xóa vẫn đúng).

## Hướng sửa

Đếm theo tập `ret_key` duy nhất (set) đã xóa, thay vì cộng dồn count từ 2 nguồn độc lập.
