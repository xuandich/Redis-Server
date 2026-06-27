# BUG-72: title/price của orchestra bị mọi view list/grouped/stats của Dashboard bỏ qua

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-26

## Problem

orchestra ghi `title`/`price` vào `result:{ret_key}` ([run.py:58](../workers/orchestra/run.py#L58)) và được orchestrator backfill bảo toàn ([main.py:197-203](../redis_server/main.py#L197)). NHƯNG các API hiển thị của Dashboard **chỉ lấy tập field cố định**, không có title/price:
- State list ([app.py:174-184](../Dashboard/app.py#L174))
- Grouped view ([app.py:257-268](../Dashboard/app.py#L257))
- Stats

→ title/price **chỉ thấy được trên trang raw JSON detail**, không xuất hiện ở bất kỳ list/group/stats nào.

## Impact

- Dữ liệu sản phẩm cào được (mục đích chính của orchestra) gần như vô hình với người vận hành.
- Severity LOW: dữ liệu vẫn nằm trong `result:{ret_key}`, không mất — chỉ là tầng hiển thị bỏ sót.

## Fix

Thêm `title`/`price` vào projection của list/grouped view (và/hoặc cột Dashboard) cho domain orchestra (hoặc generic: hiển thị các field domain-specific nếu có).

## Test

```
Submit job orchestra thành công có title/price → list/grouped view hiển thị được title/price.
```
