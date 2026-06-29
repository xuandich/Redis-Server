# BUG-93_LOW_clear_finished-/-clear_queue-dung-whitelist-status-in-['success','failed']-trong

**Severity**: LOW  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

clear_finished / clear_queue dung whitelist status in ['success','failed'] trong khi moi n…

## Details

**Location**: Dashboard/app.py:460, 535

**Description**:
clear_finished (Dashboard/app.py:460) va clear_queue_compat (app.py:535) chi xoa result co status in ['success','failed']. Nhung TAT CA view doc va cac clear khac phan loai 'failed' = status != 'success': /api/jobs (app.…

**Why Real**:
Doc code that: hai branch dung danh sach cung ['success','failed'] con 6 cho khac dung != 'success'. La divergence that trong tang phan loai. TUY NHIEN hien khong reachable voi out…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: low  
**reason**: Divergence xác nhận: Dashboard/app.py:460 (clear_finished) và 535 (clear_queue_compat) dùng `status in ['success', 'failed']`, trong khi 655 (clear_state) và 707 (clear_failed) dùng `status != 'success'`. Workers hiện chỉ ghi 'success'|'failed' nên chưa tác động, nhưng nếu schema extend (thêm status type mới) sẽ tạo hành vi không nhất quán: clear_finished bỏ qua status mới, clear_failed sẽ xóa. Là

## Impact

- Domain: dashboard-integrity
- Source: P4
