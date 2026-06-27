# BUG-71: manomano + orchestra hardcode `http_code=200` trong mark_success — metadata sai sự thật

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-26

## Problem

Cả 2 worker mới truyền **literal 200** vào `mark_success` trên nhánh thành công:
- manomano: `result.mark_success(html, {}, 200, cookies, elapsed_ms)` ([extractor.py:245](../workers/manomano/sourceCode/extractor.py#L245))
- orchestra: `result.mark_success(html, {}, 200, cookies, elapsed_ms, title=title, price=price)` ([extractor.py:273](../workers/orchestra/sourceCode/extractor.py#L273))

`mark_success` set `self.http_code = http_code` ([models.py:34-43](../workers/orchestra/sourceCode/models.py#L34)). undetected_chromedriver/Selenium **không expose HTTP status** dễ dàng → giá trị 200 là **bịa**, không phản ánh status thật của response.

> Đây KHÔNG phải nguyên nhân false-success (BUG-69/70 mới là) — đây là vấn đề **độ chính xác metadata** riêng.

## Impact

- `result.http_code` luôn = 200 trên mọi success → vô dụng cho chẩn đoán/dashboard.
- Chặn mọi hướng phân loại tương lai dựa trên http_code (như fnac làm) — không thể phân biệt 200-thật với 3xx/4xx-render.
- Severity LOW: bản thân không gây mất dữ liệu (BUG-69/70 lo phần đó), chỉ làm metadata gây hiểu nhầm.

## Fix

Hoặc (a) bỏ field http_code khỏi schema worker Selenium (không đo được → đừng bịa), hoặc (b) lấy status thật qua CDP (`Network.responseReceived`) / performance logs nếu cần. Tối thiểu: đừng hardcode 200 — để `None`/`0` khi không đo được, để downstream biết là "không có status".

## Test

```python
# mark_success không nên nhận http_code cố định 200; nếu giữ field, phải = giá trị đo thật hoặc None.
```
