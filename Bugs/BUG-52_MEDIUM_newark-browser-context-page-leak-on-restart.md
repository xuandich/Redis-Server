# BUG-52: Rò rỉ browser/context/page + playwright mỗi lần (re)start — Chromium mồ côi tích lũy, OOM-kill container

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-23

## Problem

`start_browser_with_proxy()` được gọi một lần lúc khởi động `process_urls()` và được gọi lại trên MỌI đường restart/retry. Mỗi lần gọi chỉ `await self.browser.close()` và `await self.playwright.stop()`, **không bao giờ** đóng `self.context` hay `self.page`, không set browser/context/page về None, và lại spawn một playwright HOÀN TOÀN MỚI vô điều kiện thay vì tái sử dụng.

## Root Cause

Trong [extractor.py](workers/newark/sourceCode/extractor.py#L86-L110):

```python
if self.browser:
    await self.browser.close()
if self.playwright:
    await self.playwright.stop()
self.playwright = await async_playwright().start()
```

Vấn đề: (1) `self.context` / `self.page` không bao giờ được đóng — mồ côi. (2) Một subprocess node driver playwright mới được spawn mỗi lần restart trong khi `browser.close()` cũ có thể đã race. (3) Nếu `launch()` thành công nhưng `new_context()`/`new_page()` (dòng 112-118) ném exception, browser vừa launch bị bỏ mở và hàm trả về False; vòng retry homepage tại dòng 387 bỏ qua return value và lặp tiếp, tạo thêm browser mới. Đối chiếu fnac ([extractor.py](workers/fnac/sourceCode/extractor.py#L182-L201)) làm đúng: đóng page→context→browser, mỗi cái guarded try/except, null hóa, và tái dùng playwright qua `if not self.playwright`.

## Scenario

Một job gặp proxy block: retry fetch tới 3 lần (mỗi lần restart browser) cộng tới 5 lần retry homepage. Mỗi restart đóng browser cũ nhưng để lại context/page mồ côi và spawn playwright driver mới. Một job đơn lẻ spawn và rò rỉ 5-8 Chromium cùng nhiều subprocess driver.

## Impact

Với `--disable-dev-shm-usage` và `mem_limit` Docker, các tiến trình Chromium rò rỉ làm cạn bộ nhớ container và container bị OOM-kill giữa chừng → `container.wait()` trong main.py thấy exit code khác 0 / timeout và không có result nào được ghi sạch. Ngay cả khi chưa OOM, các tiến trình node `playwright` driver tích lũy dần.

## Fix

Làm theo fnac: đóng page, rồi context, rồi browser, mỗi cái wrapped try/except và set về None; tái dùng playwright thay vì stop+restart mỗi lần:

```python
for obj_name in ('page', 'context', 'browser'):
    obj = getattr(self, obj_name, None)
    if obj:
        try:
            await obj.close()
        except Exception:
            pass
        setattr(self, obj_name, None)
if not self.playwright:
    self.playwright = await async_playwright().start()
```

Thêm guard finally để nếu `new_context`/`new_page` fail thì đóng browser vừa launch trước khi return False.

## Related

Liên quan [[BUG-newark-closed-page-reuse]] (cùng gốc: page không bao giờ null hóa) và shm-size-exceeds-mem-limit đã ghi nhận (làm trầm trọng việc OOM).
