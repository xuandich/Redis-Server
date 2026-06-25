# BUG-53: Result success báo http_code=0 — listener GraphQL có thể không bao giờ chạy, che block/captcha thành success

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-23

## Problem

`http_code` chỉ lấy từ một listener network response chỉ ghi status khi URL request chứa cả 'graphql' VÀ 'operationName=Product'. `response_data['status']` mặc định 0. Ở nhánh success, result được build với `http_code=response_data['status']` — tức là 0 mỗi khi lời gọi GraphQL cụ thể đó không được quan sát (navigation cached, dữ liệu sản phẩm về qua operation tên khác, hoặc trang block/interstitial vẫn có '/dp/' trong URL). Sau đó main.py set `status='success'` thuần dựa trên html có nội dung hay không, bỏ qua hoàn toàn http_code.

## Root Cause

Detection status bị tách rời khỏi success thật, trong [extractor.py](workers/newark/sourceCode/extractor.py#L278-L319):

```python
response_data = {'status': 0, 'headers': {}}
...
if 'graphql' in response.url and 'operationName=Product' in response.url:
    response_data['status'] = response.status
...
# nhánh success:
result = {..., 'http_code': response_data['status'], ...}   # = 0 nếu listener không khớp
```

Và quy tắc success tại [main.py](workers/newark/sourceCode/main.py#L43):

```python
r['status'] = 'success' if r.get('html') else 'failed'
```

Bất kỳ HTML non-empty nào (kể cả trang soft-block/geo-block/'access denied' rơi vào URL '/dp/' qua kiểm tra substring tại [extractor.py](workers/newark/sourceCode/extractor.py#L219)) đều được báo là crawl thành công với `http_code:0`.

## Scenario

Newark trả trang sản phẩm qua navigation cached (không phát lại lời gọi GraphQL `operationName=Product`), hoặc trả trang chặn vẫn có '/dp/' trong URL. `search_product` trả True (do '/dp/' trong URL), `response_data['status']` vẫn là 0. main.py thấy html non-empty → `status='success'`, `http_code:0`.

## Impact

Consumer polling `/api/job/{ret_key}` nhận `status=success` với `http_code:0` và HTML thực ra là trang block/lỗi. Hỏng chất lượng dữ liệu lặng lẽ: crawl fail không phân biệt được với success thật, và http_code không bao giờ dùng để lọc được vì nó là 0 đúng trên những trang mà lời gọi GraphQL bị chặn.

## Fix

Detect success dựa trên response navigation thật (hoặc kiểm tra sự hiện diện nội dung/selector sản phẩm) thay vì chỉ listener GraphQL tùy chọn; coi `http_code==0` mà có HTML là khả nghi; và trong main.py đưa http_code (cộng kiểm tra nội dung) vào quyết định success/failed thay vì chỉ dựa html-truthiness:

```python
# extractor: ghi status từ response navigation chính
main_response = await self.page.goto(url, ...)
if main_response:
    response_data['status'] = main_response.status
# main.py:
r['status'] = 'success' if (r.get('html') and 200 <= r.get('http_code', 0) < 300) else 'failed'
```

## Related

Liên quan success-result-missing-domain/timestamp đã ghi nhận và [[BUG-fnac-non-403-error-marked-success]] (cùng họ: trang lỗi bị gắn nhãn success), nhưng đây là lỗi đặc thù newark do http_code=0 từ listener GraphQL hẹp.
