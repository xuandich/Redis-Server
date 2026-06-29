# BUG-51: submit-job route theo prefix ret_key do client cung cấp thay vì URL — worker sai crawl site sai

**Severity**: MEDIUM
**Status**: FIXED
**Date**: 2026-06-23

## Problem

Endpoint `/api/submit-job` xác định domain crawl (quyết định routing queue VÀ image Docker worker nào chạy) từ **prefix ret_key do client cung cấp** thay vì từ URL. URL chỉ được dùng làm fallback khi ret_key không đúng dạng `ret_{domain}_{uuid}`. Docstring và comment dòng 802 ('extracted from URL') khẳng định route theo URL, nhưng code không làm vậy.

## Root Cause

Trong [app.py](Dashboard/app.py#L789-L828):

```python
parts = ret_key.split('_', 2)
if len(parts) >= 2 and parts[0] == 'ret':
    domain = parts[1]            # prefix ret_key thắng vô điều kiện
else:
    domain = _extract_domain_from_url(url)
...
queue_name = f'crawler:{domain}'   # dòng 805
... crawl_job(..., domain=domain)  # dòng 823
```

`domain` này được dùng cho cả tên queue và truyền nguyên văn vào `crawl_job`. Tại [main.py](redis_server/main.py#L121) chính `domain` đó chọn image worker: `image_name = f'worker-{domain}:latest'`. URL không bao giờ được validate đối chiếu với domain khai báo. Vậy client POST `{url:'https://www.newark.com/...', ret_key:'ret_fnac_<uuid>'}` sẽ enqueue vào `crawler:fnac` và spawn `worker-fnac` để crawl một URL newark.

## Scenario

Một client (hoặc client lỗi) gửi `{url: 'https://www.newark.com/product/123', ret_key: 'ret_fnac_abc'}`. Job vào queue `crawler:fnac`, image `worker-fnac` chạy và cào trang newark bằng logic extraction của fnac, cho ra result rác được ghi với `domain: 'fnac'` trong khi url là newark.

## Impact

Prefix ret_key sai/giả mạo lặng lẽ route URL đến sai queue domain và sai worker extraction. Worker fnac cào trang newark (hoặc ngược lại), tạo result rác/rỗng được ghi 'success' hoặc 'failed' mà không có dấu hiệu route sai. Vì endpoint không có auth và ret_key hoàn toàn do client kiểm soát, bất kỳ caller nào cũng có thể cross-route job, lãng phí slot worker và làm hỏng dữ liệu result. Khó chẩn đoán vì trường `domain` của result ghi 'fnac' trong khi url là newark.

## Fix

Luôn lấy domain routing từ URL qua `_extract_domain_from_url(url)`, coi prefix ret_key chỉ là consistency check:

```python
url_domain = _extract_domain_from_url(url)
parts = ret_key.split('_', 2)
if len(parts) >= 2 and parts[0] == 'ret' and parts[1] != url_domain:
    return jsonify({'success': False, 'error': f'ret_key domain {parts[1]} không khớp URL domain {url_domain}'}), 400
domain = url_domain
```

## Related

Liên quan submit-job-accepts-unsupported-domain đã ghi nhận, nhưng đây là lỗi routing theo nguồn dữ liệu sai (ret_key thay vì URL), độc lập với việc domain có được hỗ trợ hay không.
