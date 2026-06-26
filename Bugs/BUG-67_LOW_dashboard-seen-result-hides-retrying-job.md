# BUG-67: /api/jobs hiển thị job đang chạy lại là "failed" vì seen_result che job_state queued

**Severity**: LOW (display-only)
**Status**: OPEN
**Date**: 2026-06-26

## Problem

`/api/jobs` ([Dashboard/app.py:238-310](../Dashboard/app.py#L238)) scan `result:*` TRƯỚC, build `seen_result`, phân loại `status!='success'` → `'failed'` (app.py:269-272). Sau đó scan `job_state:*` và short-circuit `if ret_key in seen_result: continue` ([app.py:290-291](../Dashboard/app.py#L290)) → state `queued`/`running` bị bỏ qua. Hệ quả: nếu CÙNG `ret_key` vừa có `result:failed` cũ vừa có `job_state:queued` mới → dashboard hiển thị job đang chạy lại là **terminal failed**.

### Root Cause

- submit_job (app.py:803-840) ghi `job_state` queued + enqueue nhưng **KHÔNG xóa `result:{ret_key}` cũ**; crawl_job (main.py:82) cũng không xóa.
- Re-submit cùng `ret_key` là luồng có chủ đích (xem BUG-60). `result:failed` sống TTL 3600s (hoặc 86400s cho give-up tại orchestrator.py:218) → cùng tồn tại với `job_state:queued` trong suốt cửa sổ chạy lại.
- `seen_result` ưu tiên result cũ, che job_state mới.

> Cơ chế re-submit, KHÔNG phải retry-in-progress của RQ (verify đã bác phần đó: mọi path ghi failed result trong crawl_job đều `_clear_job_state` ngay; không có RQ Retry/on_failure; `_retry_stale_jobs` bị chặn nếu result tồn tại).
> Bất nhất phụ: `/api/jobs/<state>` không share `seen_result` giữa state → cùng ret_key hiện ở CẢ trang failed LẪN queued.

## Impact

- Display-only (không hỏng dữ liệu, cap retry vẫn đúng). Cửa sổ hẹp (cần re-submit ret_key đang có result:failed sót). Operator thấy job "failed" trong khi nó đang chạy lại.

## Fix

Khi build `/api/jobs`: nếu một `ret_key` có CẢ `result` (failed) cũ LẪN `job_state` (queued/running) với timestamp mới hơn → ưu tiên job_state (đang chạy lại). Hoặc xóa `result:{ret_key}` cũ khi re-submit/đầu crawl_job. Hoặc so timestamp result vs job_state trước khi short-circuit.

## Test

```bash
redis-cli setex result:ret_fnac_t 3600 '{"status":"failed","ret_key":"ret_fnac_t"}'
redis-cli set job_state:ret_fnac_t '{"state":"queued","ret_key":"ret_fnac_t","timestamp":9999999999}'
curl -s localhost:5000/api/jobs | python3 -c "import sys,json;d=json.load(sys.stdin);print([j for j in d if 'ret_fnac_t' in str(j)])"
# ❌ hiện: xuất hiện ở 'failed'; ✅ sau fix: ở 'queued'/'running'
```
