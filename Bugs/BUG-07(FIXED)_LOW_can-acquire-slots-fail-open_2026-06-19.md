# BUG-07: `_can_acquire_slots` fail-open khi Redis lỗi

- **Severity:** LOW
- **Status:** FIXED (2026-06-19)
- **File:** `orchestrator.py:36-38`

## Mô tả

```python
except Exception as e:
    print(f"[ERROR] Slot check failed: {e}", flush=True)
    return True  # On error, assume slots available
```

Khi Redis hiccup/timeout lúc check slot, hàm trả `True` (fail-open) → worker vẫn dequeue job.

## Hậu quả

Trong lúc Redis không ổn định, worker có thể dequeue vượt giới hạn concurrency (mọi check đều
trả True). Kết hợp với lỗi Redis, có thể spawn nhiều container hơn `MAX_CONCURRENT` dự kiến →
quá tải host (mỗi container `mem_limit=1g` + `shm_size=2g`).

Lớp Lua `_acquire_slot` trong `crawl_job` vẫn là enforcement thực sự, nên overshoot bị chặn lại
ở đó — nhưng job đã bị dequeue ra sẽ ngồi chờ trong `crawl_job` (xem BUG-06).

## Hướng sửa

Cân nhắc fail-closed (return False) khi Redis lỗi, hoặc thêm backoff trước khi thử lại, để
không dequeue ồ ạt trong sự cố Redis.
