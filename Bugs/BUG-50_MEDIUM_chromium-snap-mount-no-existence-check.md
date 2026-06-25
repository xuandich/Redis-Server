# BUG-50: CHROMIUM_SNAP_DIR bind-mount vô điều kiện, không kiểm tra tồn tại, làm hỏng mọi job trên host không có snap-chromium

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-23

## Problem

Container worker luôn được khởi chạy với volume mount `/snap/chromium/current` mà **không hề** kiểm tra đường dẫn này có tồn tại trên host hay không. Nếu host không có chromium cài qua snap đúng tại đường dẫn đó, Docker daemon từ chối bind source và `containers.run()` ném `docker.errors.APIError` cho **mọi** job của **mọi** domain.

## Root Cause

Trong [main.py](redis_server/main.py#L139-L150), thư mục snap được thêm vô điều kiện, trong khi thư mục proxy ngay bên dưới lại được bảo vệ bằng `os.path.isdir()`:

```python
volumes = {
    CHROMIUM_SNAP_DIR: {'bind': CHROMIUM_SNAP_DIR, 'mode': 'ro'},   # KHÔNG kiểm tra tồn tại
}
...
_proxy_check = _os.environ.get('PROXY_CHECK_DIR', PROXY_HOST_DIR)
if proxy_type == 'standard' and PROXY_HOST_DIR and _os.path.isdir(_proxy_check):  # proxy CÓ kiểm tra
    volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}
```

`CHROMIUM_SNAP_DIR = '/snap/chromium/current'` được hard-code tại [config.py](redis_server/config.py#L21). Bind source này do **host daemon** phân giải (orchestrator nói chuyện với `/var/run/docker.sock` của host), và nó là symlink. Không có fallback, không có validation: nếu đường dẫn vắng mặt trên host, daemon báo lỗi ngay.

## Scenario

Triển khai orchestrator lên một host mới (distro khác, chromium không cài qua snap, hoặc snap update đổi đường dẫn). Người dùng submit một job fnac. `crawl_job` gọi `containers.run(...)` với volume `/snap/chromium/current` không tồn tại trên host → APIError ngay lập tức, trước cả khi container được tạo.

## Impact

Mất dịch vụ toàn bộ: mọi `crawl_job` của mọi domain fail với lỗi APIError khó hiểu. Vì `containers.run()` ném trước `container.wait()`, exception lan đến nhánh `except` ([main.py](redis_server/main.py#L102-L110)) ghi một result failed chung chung rồi re-raise, nên dashboard hiển thị fail mờ mịt trên tất cả domain. Đường dẫn hard-code cũng khiến hệ thống không portable. Đây là single-point-of-failure mang tính hệ thống (không có container nào được tạo, khác với bug orphan-leak đã ghi nhận).

## Fix

Làm theo đúng pattern của proxy dir — chỉ thêm volume snap khi đường dẫn tồn tại, và/hoặc validate một lần lúc orchestrator khởi động để báo lỗi rõ ràng thay vì fail mỗi job:

```python
volumes = {}
if _os.path.isdir(CHROMIUM_SNAP_DIR):
    volumes[CHROMIUM_SNAP_DIR] = {'bind': CHROMIUM_SNAP_DIR, 'mode': 'ro'}
else:
    print(f'[Warning] CHROMIUM_SNAP_DIR {CHROMIUM_SNAP_DIR} không tồn tại trên host, bỏ qua mount')
```

Tốt hơn: cho phép cấu hình đường dẫn chromium qua env và validate tại startup của orchestrator để surface lỗi actionable.

## Related

Liên quan proxy-mount-ignores-proxy-type và proxy-check-host-path-inside-container đã ghi nhận — đây là cùng họ lỗi mount nhưng ở thư mục chromium chưa được bảo vệ.
