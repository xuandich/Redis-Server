# BUG-64: Fix BUG-49 bỏ sót band 3xx (300-399) → vẫn mark_success

**Severity**: LOW (trigger hiếm)
**Status**: OPEN
**Date**: 2026-06-26

## Problem

Fix BUG-49 chỉ gate `http_code == 0 or http_code >= 400` ([fnac/sourceCode/extractor.py:287](../workers/fnac/sourceCode/extractor.py#L287)), **không phủ band 3xx (300-399)**. Một response có status cuối là 3xx (vd `304 Not Modified`, hoặc redirect không được auto-follow) lọt cả block `(403,429,503)` lẫn block `>=400` → tới `result.mark_success(...)` ([extractor.py:290](../workers/fnac/sourceCode/extractor.py#L290)). Hẹp hơn chính spec của BUG-49 doc ("chỉ mark_success khi `200 <= http_code < 300`").

### Root Cause

```python
if result.http_code in (403, 429, 503): ...      # retry rồi fail
if result.http_code == 0 or result.http_code >= 400:   # ← 300-399 lọt
    result.mark_failed(...)
    return result
result.mark_success(...)   # 3xx tới đây
```

## Impact

- 3xx (đặc biệt 304) → `status='success'` với HTML có thể rỗng/cũ; `process_keys_with_retry` chỉ retry `failed` nên không retry → lưu false-success vĩnh viễn.
- Thực tế thấp: Playwright auto-follow 301/302/303/307/308, `goto` trả status của response CUỐI; mỗi crawl dùng browser `--incognito` mới nên cache trống → ít gặp 304 main-frame.

## Fix

Gate đúng dải success theo spec BUG-49:
```python
if not (200 <= result.http_code < 300):
    result.mark_failed(f'HTTP {result.http_code}')
    return result
result.mark_success(...)
```
(thay cho điều kiện `==0 or >=400` hiện tại; vẫn giữ block retry `403/429/503` phía trên).

## Test

```python
# Unit: ép response.status=304 → fetch_page phải trả status='failed'
# (mở rộng Run_Test/test_bug49_fetch_page.py thêm case 304, 301)
```
