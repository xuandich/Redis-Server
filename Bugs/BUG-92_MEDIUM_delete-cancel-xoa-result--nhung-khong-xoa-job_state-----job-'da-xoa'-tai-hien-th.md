# BUG-92_MEDIUM_delete/cancel-xoa-result:-nhung-khong-xoa-job_state:-->-job-'da-xoa'-tai-hien-th

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

delete/cancel xoa result: nhung khong xoa job_state: -> job 'da xoa' tai hien thanh phanto…

## Details

**Location**: Dashboard/app.py:422-438, 502-516

**Description**:
delete_job (Dashboard/app.py:422-438) va cancel_job_compat (app.py:502-516) chi delete key result:{ret_key}, KHONG delete job_state:{ret_key}. Trong cua so re-submit (cung ret_key) cua BUG-67, mot job co the cung luc co …

**Why Real**:
Doc code that: ca hai handler chi thao tac tren f'result:{ret_key}' va khong dung tay den f'job_state:{ret_key}'. Doi chieu main.py:_clear_job_state cho thay job_state la key doc l…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: VERIFIED BUG - REAL and NEW (not in existing Bugs/ directory). Both delete_job (Dashboard/app.py:422-438) and cancel_job_compat (app.py:502-516) ONLY delete result:{ret_key}, failing to delete job_state:{ret_key}. Since job_state has TTL=86400s (main.py:54, orchestrator.py:218), orphaned keys persist for 1 day. This creates phantom jobs when: (1) user deletes a job via /api/delete/{ret_key}, (2) j

## Impact

- Domain: dashboard-integrity
- Source: P4
