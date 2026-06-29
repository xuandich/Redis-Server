# BUG-95_MEDIUM_re-submit-after-crash-recovery-give-up-silently-resets-the-retry-cap-(cap-only-p

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

Re-submit after crash-recovery give-up silently resets the retry cap (cap only protects wh…

## Details

**Location**: redis_server/orchestrator.py:212-219; Dashboard/app.py:804-810; redis_server/main.py:56-62

**Description**:
When crash-recovery exhausts retries it writes result:{ret_key} (status=failed, error='Job failed after N retries', TTL 86400) and the job_state has already been deleted (orchestrator.py:212, then setex result at orchest…

**Why Real**:
Verified the give-up branch deletes job_state (line 212) before writing the failed result and that the failed result carries retry_count only as a substring of 'error', not a reada…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: When orchestrator.py's _retry_stale_jobs() reaches retry_count >= 3 (lines 214-219), it writes a failed result and marks permanent give-up. However, line 212 deletes job_state:{ret_key} BEFORE this check. The failed result only contains retry_count as text in the error message, not as a structured field. When a user re-submits the same ret_key via Dashboard API submit_job (app.py:821-826), the end

## Impact

- Domain: retry-lifecycle
- Source: P4
