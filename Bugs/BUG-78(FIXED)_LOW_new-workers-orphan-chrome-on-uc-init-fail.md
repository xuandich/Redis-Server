# BUG-78: manomano/orchestra rò Chrome/chromedriver mồ côi khi uc.Chrome() raise giữa init

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-27

## Problem

Trong `_start_driver_sync` ([manomano extractor.py:99-156](../workers/manomano/sourceCode/extractor.py#L99), [orchestra extractor.py:100-151](../workers/orchestra/sourceCode/extractor.py#L100)): `self.driver = uc.Chrome(..., use_subprocess=False, version_main=chrome_ver)` (manomano:149 / orchestra:144).

`uc.Chrome.__init__` spawn chromedriver (Popen) + chrome browser **TRƯỚC** khi handshake WebDriver. Nếu handshake raise (version_main lệch / chrome treo dưới Xvfb+proxy-ext), exception bay ra **trước khi phép gán `self.driver = ...` hoàn tất** → `self.driver` giữ `None`. Nhánh `except` chỉ log + `return False`, **không** giữ tham chiếu object dở → không gọi `.quit()`. Mọi cleanup sau đó gate trên `if self.driver` → không đụng chrome/chromedriver mồ côi. PID1 = python (`exec python run.py`), không reap process sống.

## Impact (đã hạ MEDIUM→LOW khi verify)

- Leak tiến trình THẬT nhưng **bounded bởi mô hình 1-job-1-container** (`detach=True remove=True`, [main.py:160-179](../redis_server/main.py#L160)): mỗi job container mới, không tích lũy GIỮA job. Trần leak = `max_retries=3` bộ chrome trong 1 job ngắn.
- Container kill ở JOB_TIMEOUT (xem BUG-74) + `remove=True` dọn sạch khi job xong → **tự lành**. Có thể góp phần job fail dưới áp lực RAM (mem_limit 1g) nhưng không OOM-tích-lũy.
- Khác BUG-23 (orphan container tầng Docker) và BUG-73 (rò /tmp/proxy_ext_*).

## Fix

Trong `_start_driver_sync`, bọc tạo driver để bắt được tham chiếu kể cả khi __init__ raise: tạo vào biến tạm rồi gán; trong `except`, nếu biến tạm có `.quit`/`.service.process` thì kill/quit. Hoặc dùng `use_subprocess=True` để uc tự quản lý + reap. Cân nhắc thêm `tini`/init-process làm PID1 trong entrypoint để reap.

## Test

```python
# Mock uc.Chrome raise sau khi spawn service.process → assert _start_driver_sync kill process con, không để mồ côi.
```
