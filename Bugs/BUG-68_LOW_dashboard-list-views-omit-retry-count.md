# BUG-68: Dashboard list view không hiển thị retry_count → không thấy job sắp chạm cap

**Severity**: LOW (observability)
**Status**: OPEN
**Date**: 2026-06-26

## Problem

`retry_count` được lưu/bảo toàn đầy đủ (main.py `_set_job_state` queued+running, orchestrator bump khi re-enqueue + cap >=3, dashboard submit preserve — BUG-60), nhưng **mọi list/overview view của dashboard đều bỏ field này** khi build job dict:
- `get_jobs_by_state`: nhánh queued/running ([app.py:99-105](../Dashboard/app.py#L99)), nhánh RQ-queue (147-152), nhánh finished/failed (174-184)
- `get_jobs`: nhánh result (257-268), nhánh job_state (294-300), nhánh RQ (344-350)
- Record give-up của orchestrator chỉ lưu STRING `'Job failed after N retries'` ([orchestrator.py:214-218](../redis_server/orchestrator.py#L214)), không có field số → sau khi job xong/give-up thì giá trị không truy lại được.

### Lưu ý (rebuttal một phần)

`/api/job_detail/<ret_key>` CÓ trả toàn bộ job_state ([app.py:217](../Dashboard/app.py#L217)) và `job_detail.html` dump "Raw Data" → `retry_count` THẤY ĐƯỢC ở trang chi tiết KHI job còn queued/running. Nhưng vô hình ở mọi list/overview → operator không quét được listing để phát hiện job sắp chạm cap; job gần-cap trông y hệt job mới. Sau khi có result, job_detail trả result trước (thiếu field số) → lịch sử retry không truy lại được.

> NEW: BUG-60 (clobber retry_count) + BUG-20 (cap) lo phần preserve/enforce, KHÔNG phải DISPLAY. Chưa bug nào phủ "dashboard không surface retry_count".

## Impact

- Thuần observability/UX; cap vẫn enforce đúng, không mất dữ liệu/sai hành vi. Operator không phân biệt được job đang retry nhiều lần với job mới trong các bảng danh sách.

## Fix

Thêm `'retry_count': data.get('retry_count', 0)` vào job dict ở mọi nhánh list (app.py:99-105, 147-152, 174-184, 257-268, 294-300, 344-350). Cân nhắc lưu `retry_count` (số) vào record give-up (orchestrator.py:214-218) để truy lại sau khi job kết thúc.

## Test

```bash
redis-cli set job_state:ret_fnac_t '{"state":"queued","ret_key":"ret_fnac_t","retry_count":2,"url":"x","domain":"fnac"}'
curl -s localhost:5000/api/jobs | grep -o 'retry_count'
# ✅ sau fix: field retry_count xuất hiện trong listing
```
