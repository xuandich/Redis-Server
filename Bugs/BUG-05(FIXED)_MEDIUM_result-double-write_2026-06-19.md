# BUG-05: Result bị ghi 2 lần vào Redis

- **Severity:** MEDIUM
- **Status:** FIXED (2026-06-19)
- **File:** `workers/fnac/run.py:44`, `main.py:99`

## Mô tả

Khi job thành công, `result:{ret_key}` bị ghi 2 lần:

1. Worker container tự ghi (`workers/fnac/run.py:44`):
   ```python
   r.setex(f"result:{ret_key}", result_ttl, json.dumps(result, ...))
   ```
2. `_spawn_and_wait_container` đọc lại key đó (`main.py:171`), trả về cho `crawl_job`, rồi
   `crawl_job` ghi đè lần nữa (`main.py:99`):
   ```python
   result = _spawn_and_wait_container(...)
   redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(result, ...))
   ```

## Hậu quả

Double-write cùng một dữ liệu. Với HTML nặng (vài trăm KB – vài MB/job), đây là chi phí
băng thông + CPU serialize không cần thiết, nhân với số lượng job.

Không gây sai logic — chỉ lãng phí.

## Hướng sửa

`crawl_job` chỉ cần đọc result (worker đã ghi), không ghi lại. Bỏ `setex` ở `main.py:99`,
giữ `_clear_job_state(ret_key)` và `return result`.

Lưu ý: vẫn giữ các nhánh ghi `error_result` (timeout/no-result) trong `_spawn_and_wait_container`
vì những trường hợp đó worker KHÔNG ghi.
