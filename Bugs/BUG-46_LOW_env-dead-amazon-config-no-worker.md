# BUG-46: `.env` có config Amazon nhưng không có `workers/amazon/` — dead config

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-22

## Problem

`.env` định nghĩa `MAX_CONCURRENT_AMAZON=3` nhưng không có `workers/amazon/` directory. Orchestrator auto-discover không tìm thấy amazon domain → không có worker nào lắng nghe queue `crawler:amazon`. Nếu ai submit job amazon → job xếp hàng mãi, không bao giờ được xử lý.

## Root Cause

[.env:23](`.env`#L23):
```ini
MAX_CONCURRENT_AMAZON=3
```

Nhưng `workers/` directory chỉ có:
```
workers/
├── Proxy/
├── fnac/
└── newark/
```

Không có `workers/amazon/`.

Orchestrator auto-discover ([orchestrator.py:69-84](orchestrator.py#L69)):
```python
for item in workers_dir.iterdir():
    if item.is_dir() and item.name != 'Proxy':
        dockerfile = item / 'Dockerfile'
        if dockerfile.exists():
            domains.append(item.name)
```
→ Amazon không được discover → không có worker thread cho `crawler:amazon` queue.

`config.py` cũng định nghĩa `QUEUE_AMAZON = 'crawler:amazon'` và `MAX_CONCURRENT_AMAZON` (dead constant, BUG-45).

## Impact

- Dead config gây confuse khi đọc `.env`
- Nếu submit job với domain `amazon` (qua `ret_key='ret_amazon_...'`) → job enqueue thành công, nhưng không bao giờ được pick up → stuck ở queued vĩnh viễn
- Không có error/warning nào được log về việc này

## Fix

**Option A**: Xóa các dòng amazon khỏi `.env` và `config.py` nếu amazon không được hỗ trợ:
```ini
# Xóa:
# MAX_CONCURRENT_AMAZON=3
```

**Option B**: Thêm `workers/amazon/` directory với Dockerfile nếu cần hỗ trợ amazon.

**Option C**: `submit_job` kiểm tra domain có worker không trước khi enqueue (BUG-16 liên quan).

## Related

- [[BUG-16]] submit_job accepts unsupported domain
- [[BUG-45]] dead constants in config.py
