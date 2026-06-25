# BUG-03: Slot leak khi process bị kill cứng → capacity tụt dần

- **Severity:** MEDIUM-HIGH
- **Status:** FIXED (2026-06-19)
- **File:** `orchestrator.py` (`_release_slot_reaper`, `_handle_horse_failure`)

## Mô tả

Slot được trả trong `finally`:

```python
finally:
    _release_slot('domain', domain)
...
finally:
    _release_slot('global', 'total')
```

`finally` chỉ chạy khi có exception hoặc return bình thường. Nếu work horse bị **SIGKILL**
(OOM, kill -9, host crash), Python bị giết ngay → `finally` **KHÔNG chạy** → slot không được DECR.

## Hậu quả

Counter `slots:domain:fnac` / `slots:global:total` phình lên và không giảm.

Lua script set `EXPIRE key 3600` mỗi lần INCR, nhưng đây là **một key counter chung** — mỗi job
mới INCR sẽ refresh TTL của chính key đó. Dưới tải liên tục, key không bao giờ hết hạn →
**slot leak vĩnh viễn**.

→ Capacity tụt dần âm thầm: hôm nay 5 concurrent, vài hôm sau còn 3, rồi 0 → kẹt hoàn toàn
cho tới khi restart (`cleanup_stale_workers` reset slot).

## Cách tái hiện

Gửi nhiều job, `docker kill` vài container đang chạy. Kiểm tra:

```bash
redis-cli get slots:domain:fnac   # giá trị không về 0 dù không còn job chạy
```

## Cách đã sửa

**Phương pháp:** `_handle_horse_failure()` trong reaper thread release slot thay cho `finally`.

Khi horse bị SIGKILL, `finally` không chạy được. Reaper phát hiện exit bất thường và gọi
`_release_slot_reaper()` — logic tương tự `_release_slot()` trong `main.py` nhưng dùng
`redis_client` của orchestrator:

```python
def _release_slot_reaper(slot_type: str, key: str):
    redis_key = f"slots:{slot_type}:{key}".encode()
    val = redis_client.decr(redis_key)
    if val < 0:
        redis_client.set(redis_key, 0)
```

`_handle_horse_failure()` gọi cả 2:
```python
_release_slot_reaper('domain', domain)
_release_slot_reaper('global', 'total')
```

**Tại sao an toàn (không double-release):**
- Horse exit code = 0 → `finally` đã chạy → reaper KHÔNG gọi `_handle_horse_failure`
- Horse bị SIGKILL (exit code ≠ 0) → `finally` không chạy → reaper release thay

Hai nhánh loại trừ nhau, không có double-release.

**File thay đổi:** `orchestrator.py`

## Liên quan

BUG-01 (reaper thread), BUG-02 (cùng trigger: horse bị kill).

## Root cause fix (2026-06-19)

Chuyển sang `SimpleWorker` — không fork, `finally` luôn chạy được (trừ khi cả orchestrator process bị kill, lúc đó restart sẽ reset slot). Slot leak do SIGKILL horse không còn xảy ra.
