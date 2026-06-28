# BUG-70: orchestra đánh dấu success dù title/price trích xuất rỗng — zero-data crawl báo finished

**Severity**: MEDIUM
**Status**: FIXED
**Date**: 2026-06-26
**Fixed**: 2026-06-28

## Problem

Worker `orchestra` gọi `result.mark_success(html, {}, 200, cookies, elapsed_ms, title=title, price=price)` ([extractor.py:270-273](../workers/orchestra/sourceCode/extractor.py#L270)) **bất kể** `_extract_product_info()` có trích được title/price hay không. Trong `_extract_product_info` ([extractor.py:153-182](../workers/orchestra/sourceCode/extractor.py#L153)), mỗi selector bọc `try/except` trả `""`:
- title: `//h1[@class='product-name']` ([extractor.py:159](../workers/orchestra/sourceCode/extractor.py#L159))
- price: `//*[@class='attributes']//div[contains(...)]` + regex ([extractor.py:166-179](../workers/orchestra/sourceCode/extractor.py#L166))

Success chỉ gate trên `not empty_page` (`len(html) < 1000`, [extractor.py:208-212](../workers/orchestra/sourceCode/extractor.py#L208)) + không CF. **Không gate trên kết quả trích xuất** → title="", price="" vẫn success.

## Scenario

```
Trang không phải sản phẩm (soft-404, redirect category, DOM đổi nhẹ) → render >1000B, không CF
  → _extract_product_info trả ("", "") (selector miss, except nuốt)
  → mark_success(html, {}, 200, title="", price="")
  → status='success', title/price RỖNG → Dashboard finished
  → zero-data crawl báo thành công, không retry
```

## Impact

- Worker orchestra là **extract-only** (schema có `title`/`price`) nhưng success không phản ánh "đã trích đúng dữ liệu" — chỉ "có HTML ≥1000B không CF".
- Mất toàn vẹn dữ liệu âm thầm. DOM đổi nhẹ (đổi class `product-name`) → toàn bộ job success với title/price rỗng mà không ai biết.
- Liên quan BUG-69 (manomano cùng họ) nhưng orchestra CÓ trích field, chỉ thiếu **gate trên field rỗng**.

## Fix

Xóa hẳn `_extract_product_info()` (title/price extraction) — orchestra chuyển thành HTML-only fetcher giống manomano. Thay bằng `_validate_product_page()`: kiểm domain (URL phải chứa `shop-orchestra.com` hoặc `orchestra.fr`) + CSS selector (`h1`, `.product-name`, v.v.). Nếu validate thất bại → trả `invalid_content` → retry với proxy mới, không mark success.

## Test

```python
# Feed HTML không khớp selector product-name → _extract_product_info trả ("","")
# → fetch phải KHÔNG trả status='success'.
```
