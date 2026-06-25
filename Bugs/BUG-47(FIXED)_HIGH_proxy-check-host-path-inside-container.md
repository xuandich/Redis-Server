# BUG-47: `os.path.isdir(PROXY_HOST_DIR)` check host path từ trong container — luôn False

**Severity**: HIGH
**Status**: FIXED
**Date**: 2026-06-22

## Problem

Proxy không bao giờ được mount vào worker containers dù `workers/Proxy/` tồn tại và start.sh set đúng path. Log orchestrator luôn hiển thị:
```
WARNING: PROXY_HOST_DIR not found ('/home/.../workers/Proxy'), running without proxy
```

## Root Cause

[main.py:140](main.py#L140) (trước fix):
```python
if proxy_type == 'standard' and PROXY_HOST_DIR and _os.path.isdir(PROXY_HOST_DIR):
    volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}
```

`PROXY_HOST_DIR` = `/home/xuandich/CODE/PO/Redis_Server/workers/Proxy` — đây là **host path**.

Code này chạy **bên trong orchestrator container**. Đường dẫn host không tồn tại trong container → `os.path.isdir()` trả về `False` → fallback `proxy_type='none'` → proxy không được mount.

`PROXY_HOST_DIR` cần thiết để truyền làm volume source cho Docker API (Docker daemon cần host path để mount vào worker containers). Nhưng không thể dùng nó để kiểm tra tồn tại từ bên trong container.

## Scenario

```
Host: workers/Proxy/buyproxies_List.xlsx tồn tại ✓
start.sh: export PROXY_HOST_DIR=/home/.../workers/Proxy ✓
docker-compose: orchestrator nhận PROXY_HOST_DIR=/home/.../workers/Proxy ✓
main.py (in container): os.path.isdir('/home/.../workers/Proxy') → False ✗
→ WARNING: PROXY_HOST_DIR not found
→ proxy_type = 'none'
→ worker container chạy không có proxy
```

## Fix

Thêm `PROXY_CHECK_DIR` — container-internal path trỏ đến cùng thư mục qua volume mount `./workers:/app/workers`:

[docker-compose.yml:36](docker-compose.yml#L36):
```yaml
environment:
  PROXY_HOST_DIR: ${PROXY_HOST_DIR}   # host path cho Docker volume mount
  PROXY_CHECK_DIR: /app/workers/Proxy  # container path để kiểm tra tồn tại
```

[main.py:141-143](main.py#L141):
```python
# Check existence via PROXY_CHECK_DIR (container-internal path to same dir).
_proxy_check = _os.environ.get('PROXY_CHECK_DIR', PROXY_HOST_DIR)
if proxy_type == 'standard' and PROXY_HOST_DIR and _os.path.isdir(_proxy_check):
    volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}
```

## Impact

- **HIGH**: Proxy hoàn toàn không hoạt động từ khi chuyển sang container-based orchestrator
- Tất cả jobs chạy với `proxy_type='none'` dù client gửi `proxy_type='standard'`
- fnac: tiếp tục chạy nhưng kém hiệu quả (no proxy)
- newark: thất bại với "No proxy available" nếu extractor yêu cầu proxy bắt buộc

## Related

- [[BUG-42]] proxy mount ignores proxy_type (đã fix)
- [[BUG-27]] proxy-host-dir relative path
