# BUG-61: register_birth name-collision làm kẹt restart worker tới ~480s

**Severity**: MEDIUM-HIGH
**Status**: FIXED (2026-06-26)
**Date**: 2026-06-26

## Problem

Restart-loop của BUG-13 tạo lại `ThreadSafeWorker` với **cùng tên** `worker-{domain}-{index}` ([orchestrator.py:107](../redis_server/orchestrator.py#L107)). RQ `Worker.bootstrap()` → `register_birth()` **raise `ValueError`** nếu key `rq:worker:{name}` còn tồn tại mà **chưa có field `death`** (rq base.py:900-902):
```python
if self.connection.exists(key) and not self.connection.hexists(key, 'death'):
    raise ValueError('There exists an active worker named {0!r} already')
```
Field `death` chỉ được ghi bởi `teardown()` → `register_death()`. Nếu Redis **còn down lúc teardown** (đúng kịch bản blip), `register_death` cũng fail → key sống với TTL `worker_ttl+60` ≈ 480s, **không có `death`**. Restart 5s sau → `register_birth` raise ValueError → bị `except Exception` của restart-loop nuốt → kẹt retry mỗi 5s **tới khi key hết TTL ~480s** (orchestrator KHÔNG re-run `cleanup_stale_workers` giữa chừng, nó chỉ chạy 1 lần lúc startup).

### Root Cause

- Tên worker cố định + key registration cũ chưa được dọn khi restart.
- `cleanup_stale_workers` ([orchestrator.py:246](../redis_server/orchestrator.py#L246)) chỉ chạy ở startup, không cứu restart giữa vòng đời.

> Phát lộ bởi BUG-13: trước đây worker chết hẳn nên không có restart → không gặp collision. Khi BUG-13 cho restart thật thì lỗi này mới reachable.

## Scenario

```
[blip] Redis down
  work() thực thi job → ConnectionError → except: break → teardown()
  register_death() cũng fail (Redis còn down) → key rq:worker:fnac-0 sống, KHÔNG có 'death', TTL 480s
restart-loop: tạo worker mới tên fnac-0 → register_birth → ValueError → except → sleep 5s → lặp
→ kẹt ~480s mới start lại được (fnac mất 1/5 worker trong ~8 phút)
```

## Impact

- Giảm concurrency per-domain tới ~8 phút sau mỗi blip-có-teardown-fail
- Log spam "crashed ... restarting in 5s" mỗi 5s

## Fix

Xóa registration cũ best-effort **trước mỗi (re)start** ([orchestrator.py:116-119](../redis_server/orchestrator.py#L116)):
```python
worker_key = f'rq:worker:{worker_name}'
try:
    redis_client.delete(worker_key)
except Exception:
    pass
```
Vì mỗi `(domain, index)` chỉ có đúng 1 thread sở hữu tên đó → xóa key cũ là an toàn, không đụng worker đang chạy thật. `register_birth` sau đó không còn thấy key → không raise.

## Test

```bash
# Giả lập key worker cũ chưa có 'death'
redis-cli hset rq:worker:worker-fnac-0 foo bar
redis-cli expire rq:worker:worker-fnac-0 480
# Restart orchestrator → worker-fnac-0 phải start được ngay (không kẹt 480s)
docker logs orchestrator 2>&1 | grep "Worker-0 listening"
```
