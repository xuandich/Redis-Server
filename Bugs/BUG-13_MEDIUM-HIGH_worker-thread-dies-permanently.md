# BUG-13: Worker thread dies permanently on Redis blip

**Severity**: MEDIUM-HIGH  
**Status**: OPEN  
**Date**: 2026-06-19

## Problem

Worker thread không tự phục hồi khi chết vĩnh viễn sau khi gặp Redis connection error.

### Root Cause

1. **[orchestrator.py:60-66](orchestrator.py#L60-L66)** — `dequeue_job_and_maintain_ttl()` loop gọi `heartbeat()` **không bọc try/except**:
```python
while not _can_acquire_slots(self.domain):
    time.sleep(1)
    self.heartbeat()  # ← Không bảo vệ, ConnectionError thoát thread
```

2. Redis blip tạm thời (network issue, restart) → `_can_acquire_slots` fail-closed trả `False` → vào loop → `heartbeat()` raise `ConnectionError` → thoát `dequeue_job_and_maintain_ttl` → `work()` crash → thread chết vĩnh viễn

3. Với N worker threads, mỗi lần blip là mất ~1-3 threads → sau vài blips là hệ thống ngừng xử lý âm thầm

### Scenario

```
Orchestrator: 5 workers fnac
[blip] Redis restart 3s
  Worker-0: heartbeat() → ConnectionError → exit
  Worker-1: heartbeat() → ConnectionError → exit
  Worker-2: heartbeat() → ConnectionError → exit
[blip over] Redis back
  Workers 0,1,2 still dead
  Hệ thống chỉ còn 2/5 workers → throughput giảm 60%
  Không reset đến restart orchestrator
```

## Impact

- Throughput giảm dần (hệ thống không realtime báo lỗi, user nhận ra rất muộn)
- Crash không bị log (heartbeat exception vỡ trước khi logger catch được)
- Chỉ phục hồi khi restart orchestrator (downtime)

## Fix

Bọc `heartbeat()` trong try/except, exponential backoff khi Redis lỗi:
```python
while not _can_acquire_slots(self.domain):
    try:
        self.heartbeat()
        time.sleep(1)
    except Exception as e:
        print(f"[{self.domain}] heartbeat failed: {e}, will retry", flush=True)
        time.sleep(min(2 ** attempt, 10))  # exponential backoff max 10s
        continue
```

Hoặc tách logic: check slots, catch error, log, retry từ outer function.

## Test

```bash
# Start orchestrator
./start.sh

# Phát hiện trong logs: số workers chạy sao với số expected?
# Khi Redis blip, heartbeat() có exception?
docker logs orchestrator 2>&1 | grep -i "heartbeat\|worker.*exit"
```
