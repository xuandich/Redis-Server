# BUG-01: Zombie process tích lũy

- **Severity:** HIGH
- **Status:** FIXED (2026-06-19, root cause fixed 2026-06-19)
- **File:** `orchestrator.py` (`ThreadSafeWorker`)

## Mô tả

`monitor_work_horse` được override thành `pass` để lách RQ ra concurrency:

```python
def monitor_work_horse(self, _job, _queue):
    """Skip death penalty monitoring - safe for threads"""
    pass
```

Trong RQ gốc (`rq/worker/worker_classes.py:74-146`), hàm này gọi `wait_for_horse()` →
`os.waitpid()` để **reap** child process. Override thành `pass` → không bao giờ gọi `waitpid`.

## Hậu quả

Mỗi job = 1 `os.fork()` work horse. Sau khi horse xong, vì không ai `waitpid`, nó trở thành
**zombie process**. Orchestrator chạy liên tục, xử lý hàng nghìn job → zombie chất đống →
cạn PID table → `fork()` fail → toàn hệ thống đứng.

Nguy hiểm nhất cho service long-running.

## Cách tái hiện

Chạy orchestrator, gửi vài trăm job, theo dõi:

```bash
ps -el | grep -c defunct   # số zombie tăng dần, không giảm
```

## Cách đã sửa

**Phương pháp:** Thêm zombie reaper thread dùng `os.waitpid(-1, WNOHANG)`.

Không khôi phục blocking `monitor_work_horse` của RQ (sẽ mất concurrency). Thay vào đó:

1. **`monitor_work_horse`** thay `pass` bằng `_register_horse(self.horse_pid, job.id, ...)` —
   lưu PID vào registry `{pid → ret_key, domain, url}` rồi return ngay (non-blocking).

2. **`_reaper_loop()`** chạy trên 1 daemon thread riêng, mỗi 0.5s:
   ```python
   while True:
       pid, raw_status = os.waitpid(-1, os.WNOHANG)
       if pid == 0:
           break  # không còn zombie
       info = _horse_registry.pop(pid, None)
       # xử lý exit code...
   ```
   `waitpid(-1, WNOHANG)` reap **bất kỳ** child nào đã exit mà không block,
   đồng thời kernel xóa entry khỏi process table → zombie biến mất.

3. **Thread được start** trong `start_orchestrator()` trước khi spawn worker threads.

**Flow sau khi fix:**
```
Thread fnac
  fork → Horse A  ──────────────────────────────► exit(0)
         [registry: pid_A → ret_key_A]              ↓
  fork → Horse B                             Reaper thread (0.5s)
         [registry: pid_B → ret_key_B]         waitpid(-1, WNOHANG)
  fork → Horse C                               → reap pid_A (zombie cleared)
         ...                                   → reap pid_B
                                               → ...
```

**File thay đổi:** `orchestrator.py`

## Liên quan

BUG-02, BUG-03 (cùng fix bởi reaper — xem thêm).


## Root cause fix (2026-06-19)

Chuyển `ThreadSafeWorker` từ `Worker` sang `SimpleWorker` — không fork nữa, không có horse process, không có zombie. Reaper code được xóa hoàn toàn (dead code).
