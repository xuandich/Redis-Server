# BUG-38: RESULT_TTL (1h) < job_state TTL (24h) → crash recovery re-crawls a finished job

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19
**Found by**: completeness critic

## Problem

`_retry_stale_jobs` quyết định job "lost" bằng `redis_client.exists(f'result:{ret_key}')`. result key hết hạn sau RESULT_TTL=3600s, nhưng job_state sống 86400s. Nếu `crawl_job` xong nhưng orchestrator crash trước `_clear_job_state` (job_state kẹt 'running'), và restart >1h sau → result đã hết hạn, job_state còn → existence check False, RQ job hash cũng hết hạn → NoSuchJobError → **re-enqueue + crawl lại URL đã phục vụ**.

### Root Cause

- result TTL = RESULT_TTL = 3600 ([config.py:25](config.py#L25))
- RQ job hash TTL = default_result_ttl = 3600 ([orchestrator.py:96](orchestrator.py#L96))
- job_state TTL = 86400 ([main.py:54](main.py#L54), [app.py:810](Dashboard/app.py#L810))

[orchestrator.py:142](orchestrator.py#L142): `if redis_client.exists(f'result:{ret_key}')` — cả 2 tín hiệu completion (result + RQ hash) sập ở mốc 1h, trong khi job_state gating sống 24h. Restart >1h sau khi job_state kẹt → NoSuchJobError (line 163) → re-enqueue (line 166-169).

## Impact

- Re-crawl URL đã phục vụ (redundant work + side-effect lặp)
- Cần job_state kẹt 'running' (crash bất thường trong window hẹp)
- Tại thời điểm re-crawl, result gốc đã hết hạn nên client cũng không lấy được nữa → không corrupt, chỉ phí

## Fix

Cho job_state TTL khớp/ngắn hơn hợp lý, hoặc đánh dấu completion bền hơn. Đơn giản: giảm job_state TTL về gần RESULT_TTL (vd 7200s) — vẫn đủ buffer recovery nhưng không để state sống lâu hơn mọi tín hiệu completion:
```python
# main.py _set_job_state: ttl=7200 thay vì 86400
```
Hoặc thêm completion marker riêng TTL dài để recovery phân biệt "đã xong, result hết hạn" vs "thật sự lost".

## Test

```bash
# Submit job, để job_state kẹt 'running' (kill orchestrator giữa result-write và _clear_job_state)
# Chờ >1h (result hết hạn), restart orchestrator
# ❌ job bị re-enqueue + crawl lại
```
