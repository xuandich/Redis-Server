# BUG-65: Fnac đánh dấu trang anti-bot/captcha HTTP 200 (Datadome) là success — không soi nội dung

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-26

## Problem

fnac phân loại success/failed **chỉ dựa trên `http_code`**, không soi response body. Anti-bot như **Datadome thường trả HTTP 200** kèm trang challenge/captcha (JS interstitial). Trang 200 này:
1. `200 in (403,429,503)` = False → bỏ qua block-retry ([extractor.py:280-286](../workers/fnac/sourceCode/extractor.py#L280))
2. `200 == 0 or 200 >= 400` = False → bỏ qua block-fail ([extractor.py:287-289](../workers/fnac/sourceCode/extractor.py#L287))
3. rơi xuống `result.mark_success(...)` ([extractor.py:290](../workers/fnac/sourceCode/extractor.py#L290)) với HTML rác

grep toàn worker fnac (extractor/main/run): KHÔNG có bất kỳ phát hiện block theo nội dung nào (datadome/captcha/challenge/content) — chỉ `page.content()` (line 275) lấy HTML, không kiểm.

### Root Cause

Gate phân loại (extractor.py:280-290) hoàn toàn theo status code; thiếu lớp content-based detection cho trang block trả 200.

> Khác BUG-49(FIXED) (non-2xx 404/429/503) và BUG-64 (band 3xx 300-399) — cả hai là vấn đề **dải status code**. BUG-65 là **HTTP 200 + body challenge** = phát hiện theo NỘI DUNG, cơ chế khác hẳn, chưa bug nào phủ.

## Scenario

```
Fnac fronts URL bằng Datadome soft-challenge → HTTP 200 + HTML captcha
  → 200 không khớp (403,429,503) và không >=400 → mark_success
  → status='success' với body challenge
  → process_keys_with_retry CHỈ retry status=='failed' (extractor.py:391-394) → KHÔNG retry
  → false-success VĨNH VIỄN, result:{ret_key} = HTML anti-bot gắn nhãn thành công
```

## Impact

- Mất toàn vẹn dữ liệu **âm thầm + vĩnh viễn** (không retry, không phân biệt được với success thật)
- Trigger có điều kiện: Datadome phải serve 200 soft-challenge thay vì hard-block (403/429/503 đã bị BUG-49 bắt) — thực tế Datadome CÓ dùng 200 cho soft challenge.

## Fix

Thêm lớp content-based block detection trước `mark_success` (extractor.py:290): nhận diện marker challenge phổ biến (vd `datadome`, `captcha-delivery`, `geo.captcha`, tiêu đề/iframe challenge, HTML quá ngắn bất thường) → `mark_failed('Blocked: anti-bot 200')` để được retry. Cân nhắc kiểm cả selector sản phẩm thật sự tồn tại (giống hướng fix BUG-53 cho newark).

## Test

```python
# Unit: feed page.content() = HTML chứa 'datadome'/'captcha-delivery' + http_code=200
# → fetch_page phải trả status='failed', không 'success'.
```
