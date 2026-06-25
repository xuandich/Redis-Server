# BUG-12: `rq:queues` smembers — replace không có tác dụng, comment sai

- **Severity:** LOW (không ảnh hưởng logic, nhưng tiềm ẩn gây nhầm lẫn)
- **Status:** FIXED (2026-06-19)
- **File:** `Dashboard/app.py:604-605`

## Mô tả

```python
raw_keys = redis_conn.smembers('rq:queues') or set()
queue_names = {k.replace('rq:queue:', '', 1) for k in raw_keys}
```

`rq:queues` là Redis set chứa **tên queue** (ví dụ: `'crawler:fnac'`), **không phải**
`rq:queue:crawler:fnac`. Do đó `.replace('rq:queue:', '', 1)` là no-op — chuỗi
`'crawler:fnac'` không chứa substring `'rq:queue:'` → không thay đổi gì.

Kết quả: `queue_names` = `{'crawler:fnac'}` — đúng với tên queue cần truyền vào
`Queue(queue_name, ...)`, **nhưng vì lý do nhầm** (no-op replace vô tình cho kết quả
đúng).

## Tại sao nguy hiểm

Nếu ai đó đọc code và hiểu `rq:queues` chứa keys dạng `rq:queue:crawler:fnac`, họ sẽ
nghĩ `.replace()` là cần thiết. Ngược lại nếu RQ thay đổi format của `rq:queues` set
trong tương lai (ví dụ thực sự lưu `rq:queue:crawler:fnac`), thì `replace` mới có tác
dụng nhưng code đã "trông đúng" từ trước → khó debug.

## Kiểm chứng

```python
# rq:queues set chứa:
redis_conn.smembers('rq:queues')  # → {'crawler:fnac'}

# NOT:
# → {'rq:queue:crawler:fnac'}
```

Có thể verify với: `redis-cli smembers rq:queues`

## Hướng sửa

Bỏ `.replace()` và đặt comment rõ ràng:

```python
raw_keys = redis_conn.smembers('rq:queues') or set()
# rq:queues chứa queue names trực tiếp (ví dụ 'crawler:fnac'), không phải Redis keys
queue_names = set(raw_keys)
```

Hoặc nếu muốn robust với cả 2 format:

```python
queue_names = {k.replace('rq:queue:', '', 1) if k.startswith('rq:queue:') else k
               for k in raw_keys}
```
