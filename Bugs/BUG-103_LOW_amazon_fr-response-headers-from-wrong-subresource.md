# BUG-103_LOW_amazon_fr: response headers lấy từ sub-resource amazon-200 bất kỳ (last-wins), không phải document sản phẩm

**Severity**: LOW  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

Listener `on_response` cập nhật `response_headers` cho **mọi** response có `'amazon' in url and status==200` → header cuối cùng (có thể là ảnh/asset/tracking/XHR con) ghi đè, không phải header của document sản phẩm chính. Metadata `headers` trong result vì vậy không đáng tin.

## Details

**Location**: workers/amazon_fr/sourceCode/extractor.py:238-244 (`on_response` + `response_headers.update(...)`), header này được trả ở :319 và ghi vào result ở :366 (`mark_success(html, headers, ...)`)

**Description**:
```
response_headers: dict = {}
async def on_response(response):
    if 'amazon' in response.url and response.status == 200:
        response_headers.update(dict(response.headers))
page.on('response', on_response)
```
`update()` gọi cho **mọi** response amazon-200 trong suốt phiên (kể cả sub-resource: JSON XHR, script, css còn qua route vì chỉ image/media bị abort ở :230-234). Header của response cuối cùng thắng — thường KHÔNG phải document HTML sản phẩm. Không có lọc theo `response.request.resource_type=='document'` hay khớp URL sản phẩm.

**Why Real**:
`headers` được ghi vào result và tiêu thụ ở downstream/dashboard như "response headers của trang". Thực tế là header của một asset ngẫu nhiên → sai lệch metadata (content-type, cache, set-cookie, cf-* ...). Không gây false-success (không dùng để phân loại) nên LOW. Cùng cơ chế BUG-83/BUG-86 (manomano) nhưng ở file amazon_fr mới.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: low  
**reason**: survives_escalation=true (2 dimension confirm). dup_guess=BUG-83/BUG-86 (manomano, file khác). amazon_fr file mới → is_new=true. LOW vì chỉ ảnh hưởng độ chính xác metadata headers, không ảnh hưởng phân loại success/failed.

## Impact

- Domain: amazon-crawl-logic
- Source: P4 (survives_escalation=true)
