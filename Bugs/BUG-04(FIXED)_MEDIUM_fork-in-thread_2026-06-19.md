# BUG-04: Fork bên trong thread → nguy cơ deadlock tiềm ẩn

- **Severity:** MEDIUM (latent, intermittent)
- **Status:** FIXED (2026-06-19)
- **File:** `orchestrator.py` (`ThreadSafeWorker`)

## Mô tả

Orchestrator chạy mỗi domain là **1 thread**:

```python
for domain in domains:
    thread = Thread(target=start_worker_for_domain, args=(domain,), daemon=True)
    thread.start()
```

Mỗi thread gọi `worker.work()` → bên trong RQ gọi `os.fork()` (`worker_classes.py:63`).

Fork một process **đa luồng** là không an toàn theo POSIX: child chỉ kế thừa thread đang gọi fork,
nhưng kế thừa toàn bộ trạng thái memory — bao gồm mọi **lock đang bị thread khác giữ** tại đúng
thời điểm fork (glibc malloc lock, logging lock, redis connection pool lock...). Các lock đó
không bao giờ được nhả trong child → child **deadlock** ngay khi chạm tới chúng.

## Hậu quả

Thỉnh thoảng một work horse treo cứng không rõ nguyên nhân (đặc biệt khi nhiều domain cùng
fork đồng thời). Khó tái hiện, khó debug, mang tính xác suất.

## Cách tái hiện

Khó tái hiện ổn định. Xác suất tăng khi: nhiều domain, tần suất fork cao, các thread cùng dùng
chung `redis_client` / logging.

## Cách đã sửa

**Phương pháp:** Chuyển `ThreadSafeWorker` từ `Worker` sang `SimpleWorker`.

`SimpleWorker` không gọi `os.fork()` — job chạy trực tiếp trong thread hiện tại, không có child process, không có vấn đề kế thừa lock.

**Thay đổi kiến trúc kèm theo:**

Vì SimpleWorker xử lý 1 job/lần và block thread trong suốt quá trình, concurrency được đạt bằng cách spawn `MAX_CONCURRENT_{DOMAIN}` threads thay vì 1 thread/domain:

```python
# Trước: 1 thread/domain
Thread(target=start_worker_for_domain, args=(domain,)).start()

# Sau: N threads/domain
for i in range(max_concurrent):
    Thread(target=start_worker_for_domain, args=(domain, i)).start()
```

Flow mới:
```
Thread fnac-0 → SimpleWorker → crawl_job() trực tiếp → container → return → job mới
Thread fnac-1 → SimpleWorker → crawl_job() trực tiếp → container → return → job mới
Thread fnac-2 → SimpleWorker → crawl_job() trực tiếp → container → return → job mới
```

Không có fork, không có horse process, không có deadlock.

**Side effect tích cực:** BUG-01/02/03 (zombie, stuck job, slot leak) được fix từ gốc — không còn horse process nào để gây ra các vấn đề đó.

**File thay đổi:** `orchestrator.py`

## Liên quan

BUG-01, BUG-02, BUG-03 (cùng root cause: fork-based Worker).
