# BUG-58: Thao tác trên page đã đóng/None sau restart thất bại gây exception giả và che lỗi thật

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-23

## Problem

Ở `attempt==1`, nếu vượt ngân sách request mỗi proxy, code gọi `await self.restart_browser_with_new_proxy()` mà KHÔNG kiểm tra return value. Hàm này có thể trả về False (proxy launch fail, hoặc homepage goto fail). Khi nó fail, `start_browser_with_proxy()` đã đóng `self.browser` nhưng để `self.page` trỏ vào page đã chết (page không bao giờ được null hóa). Thực thi rơi xuống `self.page.on(...)` và `search_product()` thao tác trên một page đã đóng.

## Root Cause

Trong [extractor.py](workers/newark/sourceCode/extractor.py#L273-L292):

```python
if attempt == 1 and self.proxies and self.request_count_per_proxy >= self.requests_per_proxy:
    ...
    await self.restart_browser_with_new_proxy()   # dòng 276 — return value bị bỏ qua
...
self.page.on('response', handle_response)         # dòng 288 — page có thể đã đóng
await self.search_product(key)                    # dòng 290
```

Kết hợp với việc `start_browser_with_proxy` không bao giờ null hóa `self.page` khi fail (dòng 86-87 đóng browser, dòng 122-124 return False mà không null page), `self.page` là tham chiếu treo tới page mà browser đã đóng. Lời gọi `self.page.on(...)` / navigation sau đó ném 'Target page/context/browser has been closed', bị bắt tại dòng 321, đốt một lượt retry với lỗi sai lệch thay vì nguyên nhân thật (proxy block / homepage timeout).

## Scenario

Proxy hết ngân sách request ở attempt 1. `restart_browser_with_new_proxy()` fail vì proxy mới bị block (return False, bị bỏ qua). Browser đã đóng, `self.page` treo. `self.page.on('response', ...)` ném 'page has been closed', bị bắt và `continue`, đốt attempt. Lặp lại đến khi cả 3 attempt cạn với lỗi 'page has been closed' sai lệch.

## Impact

Lãng phí lượt retry và surface lỗi 'page has been closed' khó hiểu trong result thay vì nguyên nhân thật (proxy block / homepage timeout). Trường hợp xấu nhất cả 3 attempt bị tiêu vào exception page-chết và job fail với chuỗi lỗi sai lệch được ghi vào `result:{ret_key}`.

## Fix

Bắt return value của `restart_browser_with_new_proxy()` và xử lý False; kết hợp null hóa page/context khi fail (xem fix bug rò rỉ browser):

```python
if attempt == 1 and ...:
    if not await self.restart_browser_with_new_proxy():
        result['error'] = 'restart proxy thất bại'
        break
```

## Related

Cùng gốc với [[BUG-newark-browser-context-page-leak-on-restart]] (self.page không được null hóa khi fail). Fix nên áp dụng đồng thời.
