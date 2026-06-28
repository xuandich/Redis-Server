# BUG-69: manomano đánh dấu success mà KHÔNG soi nội dung/sản phẩm/navigation

**Severity**: HIGH
**Status**: OPEN
**Date**: 2026-06-26

## Problem

Worker `manomano` phân loại success **không hề kiểm nội dung sản phẩm, không kiểm đã tới đúng trang, không trích field nào**. Trong `_navigate_and_get_html` ([extractor.py:158-196](../workers/manomano/sourceCode/extractor.py#L158)) chỉ có **2 tín hiệu phủ định**:
1. `cf_blocked` = title chứa `"just a moment"`/`"un instant"` hoặc html chứa `"verify you are human"` ([extractor.py:189-193](../workers/manomano/sourceCode/extractor.py#L189))
2. `empty_page` = `len(html) < 1000` ([extractor.py:194](../workers/manomano/sourceCode/extractor.py#L194))

Khi `not cf_blocked and not empty_page` → rơi thẳng xuống `result.mark_success(html, {}, 200, ...)` ([extractor.py:234-245](../workers/manomano/sourceCode/extractor.py#L234)). Grep toàn worker (extractor/main/run/models/utils/config): **KHÔNG có** `find_element`/css/xpath/`/p/`/price/title-parse/`404`/`introuvable`/redirect-check nào. Worker thuần HTML-fetcher: bất kỳ HTML ≥1000 byte không dính CF đều = success.

### Facets (gộp từ 4 finding xác nhận)

- **Không content validation** (finder worker:manomano + false-success): không selector/parse, không xác minh là trang sản phẩm.
- **Không navigation check** (extractor.py:158-196): không kiểm `driver.current_url` sau redirect. URL sản phẩm chết/hết hàng redirect về category/homepage (HTTP 200) → vẫn success. (Worker anh em newark CÓ kiểm `/dp/` + current_url tại [newark extractor.py:218-221](../workers/newark/sourceCode/extractor.py#L218) → manomano thiếu là gap thật.)
- **WebDriverWait timeout bị nuốt** ([extractor.py:182-185](../workers/manomano/sourceCode/extractor.py#L182)): `WebDriverWait(20).until(page_source>5000)` bọc `try/except: pass` → trang render dở 1000–5000 byte vẫn lọt success.

## Scenario

```
URL sản phẩm bị gỡ/hết hàng → manomano redirect về category/homepage (200, >1000B, không CF)
  → not cf_blocked and not empty_page → mark_success(html, {}, 200)
  → status='success' với HTML SAI trang
  → result:{ret_key} status=success → Dashboard passthrough (app.py:269) → finished
  → mất toàn vẹn dữ liệu âm thầm + vĩnh viễn (không retry vì không phải 'failed')
```

## Impact

- Trang soft-404 / "produit introuvable" / category / homepage / trang lỗi server (render ≥1000B) đều báo success với HTML rác.
- Cùng họ false-success với BUG-49(fnac)/BUG-53(newark)/BUG-65(fnac) nhưng **cơ chế khác hẳn**: manomano KHÔNG có cả http_code-gate LẪN content-detection — chỉ CF-title check + ngưỡng 1000 byte.

## Fix

Thêm lớp validation dương trước `mark_success` ([extractor.py:245](../workers/manomano/sourceCode/extractor.py#L245)): (1) kiểm `driver.current_url` còn là trang sản phẩm (marker `/p/` hoặc selector tên/giá tồn tại); (2) nâng ngưỡng empty_page hợp lý + không nuốt WebDriverWait timeout thành success. Trang không đạt → `mark_failed(...)` để được retry.

## Test

```python
# Feed HTML category/homepage (>1000B, không CF, không marker sản phẩm) + current_url đã redirect
# → _fetch_sync phải trả status='failed', KHÔNG 'success'.
```
