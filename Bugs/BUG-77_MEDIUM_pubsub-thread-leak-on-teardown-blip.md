# BUG-77: Redis blip lúc teardown rò rỉ PubSubWorkerThread + connection mỗi lần restart worker

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-27

## Problem

Restart-loop của BUG-13 ([orchestrator.py:110-140](../redis_server/orchestrator.py#L110)) cho `worker.work()` chạy lại vô hạn. Mỗi `work()` → `bootstrap()` → `subscribe()` tạo **1 PubSubWorkerThread daemon** (rq/worker/base.py:1044-1051, `run_in_thread`). Thread này CHỈ dừng bởi `unsubscribe()` trong `teardown()`.

Nhưng `teardown()` (rq/worker/base.py:1211-1216) gọi `register_death()` **TRƯỚC** `unsubscribe()`, **không** try/except. `register_death()` dùng pipeline `p.execute()` → raise `ConnectionError` nếu Redis down (orchestrator dùng `Redis(decode_responses=False)`, không retry/health_check). Exception lan ra → **`unsubscribe()` bị skip** → PubSubWorkerThread mồ côi.

Thread mồ côi không tự chết: `_pubsub_exception_handler` nuốt ConnectionError (`sleep 2.0`, không raise) → spin mãi; khi Redis lên lại auto-resubscribe, idle 60s vĩnh viễn, không bao giờ `close()` connection. Exception ra khỏi `work()` bị `except` nuốt ([orchestrator.py:138](../redis_server/orchestrator.py#L138)) → restart → `subscribe()` mới → **+1 thread + 1 connection**.

## Scenario

```
Redis blip mid-job, còn down lúc work() finally:teardown()
  → register_death() raise ConnectionError → unsubscribe() bị skip
  → PubSubWorkerThread cũ mồ côi (spin 2s khi down / idle 60s khi up)
  → restart-loop tạo ThreadSafeWorker MỚI → subscribe() mới → +1 thread/+1 conn
  → tích lũy 1 thread + 1 connection / worker / blip-có-teardown-fail
```

## Impact

- Rò daemon thread + Redis connection tích lũy trong process orchestrator dài hạn (nhiều worker × nhiều blip). Không sập tức thì → MEDIUM (rò chậm, không bùng nổ), nhưng **không bao giờ được dọn** tới khi restart orchestrator → cạn connection pool + tăng CPU/RAM ngầm.
- **Chỉ lộ do BUG-13**: trước đây worker chết hẳn không restart → không tạo thêm thread. Restart-loop làm hệ quả này reachable.

## Khác BUG-61

BUG-61 (FIXED) về `register_birth` ValueError "active worker already exists" → fix `redis_client.delete(rq:worker:{name})`. Fix đó chỉ xóa key Redis, **KHÔNG** gọi `stop()` trên pubsub thread mồ côi của vòng trước → leak này vẫn nguyên. Hai hệ quả khác nhau của cùng root-ordering (register_death-trước-unsubscribe).

## Fix

Trong restart-loop, giữ tham chiếu worker cũ và gọi `worker.pubsub_thread.stop()` / `worker.unsubscribe()` best-effort trước khi tạo worker mới; HOẶC bọc `register_death()` của RQ teardown (monkeypatch/subclass) trong try/except để `unsubscribe()` luôn chạy. Cân nhắc dùng `Redis(health_check_interval=...)` để giảm tần suất.

## Test

```python
# Mock register_death raise ConnectionError → đảm bảo unsubscribe()/pubsub_thread.stop() vẫn được gọi
# trên worker cũ trước khi restart; đếm threading.active_count() không tăng qua nhiều vòng restart.
```
