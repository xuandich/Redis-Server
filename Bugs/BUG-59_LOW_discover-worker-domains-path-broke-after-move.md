# BUG-59: discover_worker_domains() phân giải workers/ tương đối với redis_server/ sau khi move file, trả về 0 domain khi chạy ngoài /app

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-23

## Problem

`workers_dir = Path(__file__).parent / 'workers'`. Sau khi `orchestrator.py` được move từ repo root vào `redis_server/`, `Path(__file__).parent` là `<repo>/redis_server`, nên phân giải thành `<repo>/redis_server/workers` — thư mục không tồn tại (workers/ nằm ở repo root). Trong container nó vẫn chạy được chỉ vì Dockerfile COPY orchestrator.py vào `/app/` và docker-compose bind-mount `./workers:/app/workers`, làm `/app/workers` tồn tại. Với mọi invocation local/dev, `discover_worker_domains()` không tìm thấy gì và `start_orchestrator()` in cảnh báo rồi return — không worker nào khởi động.

## Root Cause

Trong [orchestrator.py](redis_server/orchestrator.py#L71):

```python
workers_dir = Path(__file__).parent / 'workers'   # -> <repo>/redis_server/workers (không tồn tại)
```

Và tại [orchestrator.py](redis_server/orchestrator.py#L238-L240):

```python
if not domains:
    print("[Warning] No worker domains found in workers/")
    return
```

Đường dẫn neo vào thư mục của file nguồn (`__file__`) — vốn đã move — thay vì neo vào project root hay vị trí `/app/workers` đã biết của container. Container che giấu bug nhờ trùng hợp COPY+bind-mount; đường dẫn local giờ đã sai.

## Scenario

Dev chạy `python redis_server/orchestrator.py` để debug local. `Path(__file__).parent / 'workers'` = `<repo>/redis_server/workers` không tồn tại → `discover_worker_domains()` trả `[]` → `start_orchestrator()` in '[Warning] No worker domains found in workers/' và return. Không thread worker nào khởi động, không job nào được xử lý.

## Impact

Chạy orchestrator ngoài layout container chính xác (debug local, test, hoặc image tương lai nơi workers/ không bind-mount như sibling của orchestrator.py) lặng lẽ phát hiện 0 domain và không khởi động worker thread nào, nên không job nào được xử lý. Coupling mong manh với một layout mount cụ thể.

## Fix

Phân giải workers/ tường minh, ưu tiên env var với default container, hoặc dùng project root thay vì `Path(__file__).parent`; tối thiểu coi 'không tìm thấy domain' là lỗi cứng thay vì return lặng lẽ:

```python
import os
workers_dir = Path(os.environ.get('WORKERS_DIR', '/app/workers'))
if not workers_dir.is_dir():
    workers_dir = Path(__file__).resolve().parent.parent / 'workers'  # fallback repo root
...
if not domains:
    raise RuntimeError(f'Không tìm thấy worker domain nào trong {workers_dir}')
```

## Related

Đây là bug path mới do đợt move config.py/main.py/orchestrator.py vào redis_server/, độc lập với các bug đã ghi nhận.
