# BUG-99_HIGH_amazon_fr: navigation HTTP status never checked → http_code hardcoded 200, success gated only on DOM selector

**Severity**: HIGH  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

amazon_fr (worker MỚI, Playwright): `page.goto()` vứt bỏ object Response nên HTTP status thật không bao giờ được kiểm; success chỉ dựa DOM selector và `mark_success()` ghi `http_code=200` cứng → trang lỗi/throttle của Amazon (403/429/503/404) vẫn bị phân loại `status=success` → false-success, silent data corruption.

## Details

**Location**: workers/amazon_fr/sourceCode/extractor.py:286 (goto vứt Response), :315 (`_is_product_page` là gate duy nhất), :366 (`mark_success(..., 200, ...)`) ; workers/amazon_fr/sourceCode/models.py:34-41 (gán http_code=200, status='success')

**Description**:
Trong `_navigate_and_extract`, `await page.goto(url, wait_until='domcontentloaded', timeout=45000)` (extractor.py:286) **vứt bỏ object Response** — `.status` không được đọc ở bất kỳ đâu cho navigation sản phẩm. Grep `.status` toàn worker chỉ trả về :102 (IP-check ipwho.is) và listener `on_response` (:241 `if 'amazon' in response.url and response.status == 200`) — listener này CHỈ dùng để nạp headers khi 200, KHÔNG fail job khi non-200.

Success gate DUY NHẤT là DOM: `is_product = await self._is_product_page(page)` (:315), kiểm `['#productTitle', '#title', '#add-to-cart-button', '#buybox']` (:210). Khi `is_product=True`, `fetch_url` gọi `result.mark_success(html, headers, cookies, 200, elapsed_ms)` với **literal 200** (:366) → `models.py:34,38,40` gán `http_code=200, status='success'`. Không có nhánh nào kiểm 403/429/503, `http_code==0`, hay 3xx/4xx.

Đây là **lệch chuẩn** so với fnac: `workers/fnac/sourceCode/extractor.py:271` đọc `response.status` thật, :280 retry 403/429/503, :287-288 `http_code==0 or >=400 → mark_failed`. amazon_fr dùng Playwright nên `.status` hoàn toàn có sẵn (khác Selenium ở BUG-71) → đây là thiếu sót thật, không phải giới hạn framework.

Dashboard tin tuyệt đối field `status`: `Dashboard/app.py:169 is_finished = (state=='finished' and job_status=='success')`; `http_code` chỉ hiển thị (:179, :262), KHÔNG dùng để reclassify. `main.py:82-88` và `run.py:55` truyền thẳng result không đổi.

**Why Real**:
Amazon (chống bot rất mạnh) thường trả trang lỗi/soft-error/throttle kèm HTTP 403/429/503/404 nhưng body vẫn chứa layout header có `#title` (và `75001` sau `_change_delivery_address`) → `is_product=True` → worker ghi `http_code=200, status=success` → Dashboard xếp `finished` → downstream tiêu thụ HTML rác/không-phải-sản-phẩm như thể thành công. Cùng lớp lỗi mà fnac (BUG-49/64/65) đã được vá — nay tái phát trong file amazon_fr hoàn toàn mới.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: high  
**reason**: Xác minh trên code hiện tại + escalation (refuter độc lập không bác được qua 4 hướng: guard CF/postal/captcha không phải status-guard; downstream không reclassify; Playwright có `.status` nên không phải giới hạn framework; BUG-84 là orchestra file khác, BUG-71 là Selenium metadata "không phải false-success"). amazon_fr thêm ở commit ceee225, extractor sửa ở 1cc22f3 SAU audit 06-29 → chưa từng audit → is_new=true.

## Impact

- Domain: amazon-false-success
- Source: P4 (find→verify→escalate, survives_escalation=true, 3 dimension độc lập cùng xác nhận)
