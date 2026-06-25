# BUG-17: TOCTOU race in slot pre-check before dequeue

**Severity**: LOW  
**Status**: OPEN  
**Date**: 2026-06-19

## Problem

Slot pre-check ([orchestrator.py:24](orchestrator.py#L24)) là soft check, sau đó job được dequeue. Khi **nhiều worker threads** của domain khác nhau kiểm tra cùng lúc:
- Worker-fnac: pre-check pass (global: 8/10, fnac: 4/5)
- Worker-amazon: pre-check pass (global: 8/10, amazon: 2/3)
- Cả 2 dequeue → sau 60s global slot full → job fail "Global slot timeout"

Race condition **Time-of-check vs Time-of-use (TOCTOU)**: pre-check result không còn valid sau khi trả về.

### Root Cause

[orchestrator.py:60-66](orchestrator.py#L60-L66) — check-then-dequeue:
```python
def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
    while not _can_acquire_slots(self.domain):  # ← TIME-OF-CHECK
        time.sleep(1)
        self.heartbeat()
    
    return super().dequeue_job_and_maintain_ttl(timeout, max_idle_time)  # ← TIME-OF-USE (gap here)
```

Giữa check và dequeue, thread khác có thể:
- Acquire slot từ Redis (increment counter)
- Dequeue + spawn container
→ Lúc job này dequeue, global counter có thể vượt limit rồi

### Scenario

```
fnac-worker-0: check_slots() → global:9/10 ✓, fnac:4/5 ✓ → proceed
amazon-worker-0: check_slots() → global:9/10 ✓, amazon:2/3 ✓ → proceed
fnac-worker-1: check_slots() → global:9/10 ✓, fnac:4/5 ✓ → proceed

[All 3 dequeue immediately]

Redis acquire:
  fnac-worker-0: global++→10, fnac++→5 ✓
  amazon-worker-0: global++→11, amazon++→3 ✗ (global > 10!)
  fnac-worker-1: blocked, wait... → timeout

Job2 (amazon): "Global slot timeout" fail (không phải fault của job)
```

### Impact

- **Multi-domain** concurrency scenario → workers tranh slot → ngẫu nhiên fail với "slot timeout"
- Job fail không phải do logic lỗi
- Single-domain safe (chỉ 1 domain → pre-check đủ tight)
- Không phải lỗi nghiêm trọng nhưng gây confusion

### Root Cause Deeper

Phương án 1 (hiện tại): soft pre-check + hard acquire trong job
- ✓ Không block worker khi slots full (worker sleep, không dequeue)
- ✗ TOCTOU race khi 2+ domains cùng acquire

Phương án 2 (atomic): acquire slot **trong pre-check** (một operation)
- ✓ Atomic, không TOCTOU
- ✗ Worker block nếu acquire fail (mất heartbeat)
- ✗ Phức tạp hơn

## Fix (Optional)

Hiện tại không critical. Tương lai có thể:
1. Reduce timeout từ 60s → 5s (detect fail nhanh hơn)
2. Retry logic: nếu "Global slot timeout", re-enqueue job (retry)
3. Hoặc atomic slot acquire trong dequeue (phức tạp)

## Test

```bash
# Setup: MAX_CONCURRENT_FNAC=2, MAX_CONCURRENT_AMAZON=2, MAX_CONCURRENT_TOTAL=3

# Submit 5 fnac + 5 amazon jobs simultaneously
for i in {1..5}; do
  python test_api_job.py "https://www.fnac.com/$i" "fnac" &
  python test_api_job.py "https://www.amazon.fr/$i" "amazon" &
done

# Monitor: some should timeout "Global slot timeout" (not job logic error)
# Check logs: job failed but worker was ready
```

**Note**: Bug này hiếm vì:
1. Cần 2+ domains chạy concurrent
2. Cần pre-check overlap chính xác (narrow window)
3. Single-domain systems (only fnac) không gặp
