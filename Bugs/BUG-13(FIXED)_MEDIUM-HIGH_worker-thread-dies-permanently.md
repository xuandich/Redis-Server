# BUG-13: Worker thread dies permanently on Redis blip

**Severity**: MEDIUM-HIGH  
**Status**: FIXED (2026-06-26)  
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

## Fix Applied (2026-06-26) — 2 LỚP

> Bản fix đầu (chỉ bọc `dequeue_job_and_maintain_ttl`) **không trọn vẹn**: nó chỉ cứu nhánh **chờ slot**. Redis blip lúc `execute_job()`/`heartbeat()` khiến `rq.Worker.work()` (RQ 2.9.1) bắt `redis.TimeoutError`/`except:` rồi **`break` + return BÌNH THƯỜNG** (chỉ `SystemExit` mới raise) → restart-loop ban đầu `break` luôn → thread vẫn chết. Phải fix 2 lớp:

**Lớp 1 — slot-wait** ([orchestrator.py:60-76](../redis_server/orchestrator.py#L60)): bọc `_can_acquire_slots`+`heartbeat()` trong try/except, exponential backoff 5→10→20→40→60s, reset 0 khi Redis OK.

**Lớp 2 — restart loop** ([orchestrator.py:97-140](../redis_server/orchestrator.py#L97)): vì cấu hình này (`burst=False`, no signal handler, no `max_jobs`/`max_idle_time`) → `work()` return ĐỒNG NGHĨA lỗi cần restart → **restart trên MỌI lần work() return** (không `break`), chỉ dừng khi `KeyboardInterrupt`/`SystemExit`. Thêm `redis_client.delete(rq:worker:{name})` trước mỗi (re)start để tránh `register_birth` ValueError "active worker already exists" (kẹt tới ~480s) khi `register_death` fail lúc Redis còn down (xem BUG-61).

## Test

```bash
# Start orchestrator
./start.sh

# Phát hiện trong logs: số workers chạy sao với số expected?
# Khi Redis blip, heartbeat() có exception?
docker logs orchestrator 2>&1 | grep -i "heartbeat\|worker.*exit"
```
