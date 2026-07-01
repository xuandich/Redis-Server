# BUG-101_MEDIUM_amazon_fr: gate trang sản phẩm dùng selector `#title` quá lỏng + URL không normalize về /dp/ trên đường Redis → mở rộng bề mặt false-success

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

`_is_product_page` coi trang là product nếu tìm thấy **bất kỳ** một trong `['#productTitle','#title','#add-to-cart-button','#buybox']` — `#title` là wrapper layout chung của Amazon (có cả trên search/category/interstitial). Kết hợp: `clean_amazon_url` (chuẩn hóa /dp/ASIN) CHỈ gọi trên đường batch, KHÔNG gọi trên đường Redis worker → URL non-product crawl nguyên trạng vẫn có thể vượt gate và bị `mark_success`.

## Details

**Location**: workers/amazon_fr/sourceCode/extractor.py:208-214 (đặc biệt `#title` ở :210) ; workers/amazon_fr/sourceCode/main.py:30 (clean_amazon_url gọi trong `read_urls` batch) vs :58-88 (`process_single_request` — đường Redis — KHÔNG gọi) ; utils.py:52-59

**Description**:
`_is_product_page` (:208-214) return True ngay khi 1 selector match. `#productTitle`/`#buybox`/`#add-to-cart-button` là marker đặc hiệu product, nhưng `#title` là id layout generic → xuất hiện trên nhiều template không-phải-product.

Trên đường Redis thật: `run.py:7 (URL từ env)` → `run.py:43 request={'url': url,...}` → `process_single_request` (main.py:58) → `fetcher.fetch_url(url,...)` (main.py:79) crawl URL **nguyên trạng**. `clean_amazon_url` (utils.py:52) chỉ được gọi trong `read_urls` (batch Excel, main.py:30). Vì vậy một URL search/category (`/s?k=...`, `/b?node=...`) không bị chuẩn hóa, vượt các guard trước đó (CF :292, postal :306, captcha :311 đều không phân biệt product vs search) và nếu trang có `#title` → `is_product=True` → `mark_success` ghi `status=success` với HTML không-phải-sản-phẩm.

So sánh: manomano có kiểm path-marker `if '/p/' not in current_url` trong `_validate_product_page`; amazon_fr KHÔNG có bất kỳ kiểm tra URL/path nào, chỉ dựa selector.

**Why Real**:
Cùng loại lỗi gate-quá-rộng như orchestra BUG-89 (dựa `h1` chung) nhưng ở amazon_fr. Compound với BUG-99 (không kiểm status): một trang search/aggregation trả 200 có `#title` → success với HTML rác. Bề mặt false-success rộng hơn khi client submit URL không chuẩn.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: survives_escalation=true, dup_guess=none. BUG-89 cùng CLASS nhưng worker orchestra/file khác/cơ chế h1+domain-substring. Đây là sibling ở amazon_fr (file mới). Medium: cần URL non-product được submit (URL product là ca thường) và 2/4 selector vẫn đặc hiệu — bề mặt là `#title` + thiếu normalize.

## Impact

- Domain: amazon-false-success
- Source: P4 (survives_escalation=true)
