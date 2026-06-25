# BUG-49: Trang lỗi HTTP non-403 (404/429/500/502/503) và response null bị ghi là status='success'

**Severity**: MEDIUM-HIGH
**Status**: FIXED
**Date**: 2026-06-23

## Problem

Trong `fetch_page`, chỉ HTTP 403 được coi là failure. Mọi status code non-2xx khác (404 Not Found, 429 Too Many Requests, 500/502/503 lỗi server/anti-bot) đều rơi xuống `result.mark_success(...)`, nên result được trả về với `status='success'` và html của trang lỗi/block/captcha. Trường hợp `response is None` (http_code=0) cũng chảy vào `mark_success` với nội dung trang bất kỳ.

## Root Cause

Trong [extractor.py](workers/fnac/sourceCode/extractor.py#L280-L288), chỉ 403 được special-case:

```python
if response:
    result.http_code = response.status
else:
    result.http_code = 0
result.html = await self.page.content()
...
if result.http_code == 403:
    ... result.mark_failed('HTTP 403 Forbidden')
    return result
result.mark_success(result.html, result.headers, result.http_code, ...)
return result
```

Không có nhánh nào cho dải 4xx/5xx tổng quát hay `http_code == 0`. 429 (rate-limit) và 503 (interstitial Cloudflare/anti-bot) — chính là các mã block phổ biến nhất của Fnac sau 403 — được báo là success đầy đủ với HTML rác.

## Scenario

Fnac trả 429 (quá nhiều request) hoặc 503 (trang chặn anti-bot). `response.status` là 429/503, không phải 403, nên code bỏ qua nhánh failure và gọi `mark_success` với HTML của trang chặn. Result `status='success'` được ghi vào `result:{ret_key}` và polling dashboard nhận về một thành công giả.

## Impact

Thành công giả lặng lẽ: caller không phân biệt được trang sản phẩm thật với trang block 429/503 hay 404. Result crawl bị nhiễm HTML lỗi/anti-bot gắn nhãn 'success', và tầng retry (`process_keys_with_retry`) không bao giờ retry chúng vì chỉ retry `status=='failed'`. Mất toàn vẹn dữ liệu trên toàn pipeline.

## Fix

Coi cả dải non-success là failure, retry (ưu tiên xoay proxy) với 429/503 rồi mark_failed nếu vẫn lỗi:

```python
if result.http_code == 0 or result.http_code >= 400:
    if result.http_code in (403, 429, 503) and retries_left:
        # xoay proxy + retry
        ...
    result.mark_failed(f'HTTP {result.http_code}')
    return result
result.mark_success(result.html, result.headers, result.http_code, ...)
```

Chỉ `mark_success` khi `200 <= http_code < 300`.

## Related

Liên quan retry-drops-failed-jobs-no-result đã ghi nhận ở tầng RQ, nhưng đây là lỗi phân loại success/failed sai ở tầng extractor fnac (mã non-403).
