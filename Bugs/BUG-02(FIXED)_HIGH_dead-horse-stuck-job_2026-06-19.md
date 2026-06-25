# BUG-02: Work horse chết bất thường → job kẹt vĩnh viễn

- **Severity:** HIGH
- **Status:** FIXED (2026-06-19)
- **File:** `orchestrator.py` (`monitor_work_horse`, `_handle_horse_failure`)

## Mô tả

RQ gốc dùng `monitor_work_horse` để phát hiện work horse chết bất thường và gọi
`handle_job_failure` (`rq/worker/worker_classes.py:137-146`). Vì code override thành `pass`,
parent **không monitor** child nữa.

Nếu container/horse bị **SIGKILL** (OOM do `mem_limit=1g`, docker daemon lỗi, host hết RAM)
TRƯỚC khi kịp ghi `result:{ret_key}`:

- RQ gốc: parent phát hiện qua `waitpid` → mark job failed.
- Code này: không ai biết horse đã chết.

## Hậu quả

- `job_state:{ret_key}` kẹt ở `running` (hoặc `queued`), không bao giờ có `result:{ret_key}`.
- Dashboard treo job ở trạng thái running mãi mãi.
- Client poll kết quả vô tận (cho tới timeout phía client).
- Chỉ `_retry_stale_jobs()` lúc **restart orchestrator** mới phát hiện và re-enqueue.

## Cách tái hiện

Gửi job, trong lúc container đang chạy `docker kill <container>` (mô phỏng OOM/crash).
Quan sát: job không bao giờ chuyển sang failed, không có result key.

## Cách đã sửa

**Phương pháp:** Reaper thread phát hiện exit code bất thường → gọi `_handle_horse_failure()`.

Khi `os.waitpid(-1, WNOHANG)` trả về một PID với exit code khác 0 hoặc bị signal:

```python
if os.WIFSIGNALED(raw_status) or (os.WIFEXITED(raw_status) and os.WEXITSTATUS(raw_status) != 0):
    _handle_horse_failure(pid, info)
```

`_handle_horse_failure()` thực hiện:
1. Ghi `result:{ret_key}` với `status: failed` và error message vào Redis
2. Xóa `job_state:{ret_key}` để dashboard không treo ở running
3. Release cả 2 slot (domain + global) vì `finally` trong `crawl_job` không chạy được

**Flow khi horse bị SIGKILL:**
```
Horse A  ──► SIGKILL (OOM)
              ↓ exit với signal
Reaper thread:
  waitpid(-1, WNOHANG) → (pid_A, signal_status)
  WIFSIGNALED == True
  → _handle_horse_failure(pid_A, {ret_key_A, domain, url})
    → setex result:ret_key_A  {"status": "failed", "error": "Worker killed..."}
    → delete job_state:ret_key_A
    → DECR slots:domain:fnac
    → DECR slots:global:total
```

**File thay đổi:** `orchestrator.py`

## Liên quan

BUG-01 (reaper thread), BUG-03 (slot release trong _handle_horse_failure).

## Root cause fix (2026-06-19)

Chuyển sang `SimpleWorker` — không có horse process → không có trường hợp horse bị SIGKILL → bug không thể xảy ra.
