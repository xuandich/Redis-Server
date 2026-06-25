# BUG-48: clear_state('queued') double-prefix key RQ queue, job queued thật không bao giờ bị xóa (báo 'deleted' giả)

**Severity**: MEDIUM-HIGH
**Status**: OPEN
**Date**: 2026-06-23

## Problem

Endpoint `/api/clear_state/queued` đọc set `rq:queues` để liệt kê queue rồi truyền thẳng từng phần tử làm **tên** queue cho `Queue(queue_name, ...)`. Nhưng RQ lưu **full Redis key** trong set đó (ví dụ `rq:queue:crawler:fnac`), không phải tên trần `crawler:fnac`. Tạo `Queue('rq:queue:crawler:fnac')` cho ra `q.key == 'rq:queue:rq:queue:crawler:fnac'` (bị prefix hai lần). Kết quả: `q.get_job_ids()` trả về `[]` và `q.empty()` dọn một queue không tồn tại. Chỉ các key `job_state:*` có `state=='queued'` bị xóa; còn job RQ thật vẫn nguyên vẹn.

## Root Cause

Trong [app.py](Dashboard/app.py#L609-L617):

```python
raw_keys = redis_conn.smembers('rq:queues')   # phần tử là 'rq:queue:crawler:fnac'
for queue_name in queue_names:
    q = Queue(queue_name, connection=redis_conn)   # tên đã có prefix 'rq:queue:' -> q.key = 'rq:queue:rq:queue:crawler:fnac'
    for jid in q.get_job_ids():                    # rỗng
        deleted_keys.add(jid)
    q.empty()                                      # no-op trên queue thật
```

Kiểm chứng với RQ 2.9.1: `Queue.enqueue_job` gọi `pipe.sadd(self.redis_queues_keys, self.key)` lưu `self.key == 'rq:queue:<name>'`. Bản thân RQ khi enumerate dùng `to_queue(rq_key)` để strip prefix; code này thì không. Đối chiếu nhánh đọc đúng tại [app.py](Dashboard/app.py#L117) là `queue_name = k.replace('rq:queue:', '')`.

## Scenario

Queue `crawler:fnac` có 5 job đang chờ. Operator bấm 'clear queued' trên dashboard. Endpoint tạo `Queue('rq:queue:crawler:fnac')`, `get_job_ids()` rỗng, `empty()` no-op. API trả `{'success': True, 'deleted': N}` (N chỉ đếm job_state keys), nhưng 5 job RQ thật vẫn còn và worker tiếp tục pick chúng để chạy.

## Impact

Lỗi toàn vẹn dữ liệu / lòng tin operator: UI báo queue đã clear trong khi crawl vẫn tiếp tục bắn, lãng phí slot/proxy và tạo result cho URL mà người dùng tưởng đã hủy. Số `deleted` báo cáo chỉ phản ánh job_state keys, không bao giờ là job RQ thật.

## Fix

Strip prefix trước khi tạo Queue, hoặc dùng `rq.Queue.all()` parse đúng key đã đăng ký:

```python
from rq import Queue
for q in Queue.all(connection=redis_conn):
    for jid in q.get_job_ids():
        deleted_keys.add(jid)
    q.empty()
```

Hoặc thủ công: `name = queue_name[len('rq:queue:'):] if queue_name.startswith('rq:queue:') else queue_name` rồi `Queue(name, connection=redis_conn)`.

## Related

Liên quan rq-queues-misleading-replace và stop-clear-false-success đã ghi nhận, nhưng đây là lỗi double-prefix cụ thể khiến endpoint clear queued hoàn toàn vô hiệu.
