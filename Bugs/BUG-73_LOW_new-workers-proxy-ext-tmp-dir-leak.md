# BUG-73: `_create_proxy_auth_extension` rò rỉ thư mục `/tmp/proxy_ext_*` khi exception

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-26

## Problem

Cả 2 worker dùng `_create_proxy_auth_extension` tạo thư mục tạm qua `mkdtemp` rồi ghi extension zip:
- manomano ([extractor.py:51-63](../workers/manomano/sourceCode/extractor.py#L51))
- orchestra ([extractor.py:54-65](../workers/orchestra/sourceCode/extractor.py#L54))

Nếu `zipfile`/`os.remove`/ghi file **raise sau `mkdtemp`**, nhánh `except` trả `None` **không `shutil.rmtree`** thư mục đã tạo → `/tmp/proxy_ext_*` còn lại vĩnh viễn.

## Impact

- Mỗi job lỗi (trên nhánh này) để lại 1 thư mục tạm trong container `/tmp`.
- Severity LOW: container `remove=True` ([main.py:175](../redis_server/main.py#L175)) → `/tmp` biến mất khi container kết thúc, nên rò rỉ **bị giới hạn trong vòng đời 1 container** (không tích lũy giữa các job vì mỗi job 1 container). Chỉ tích lũy nếu container sống lâu chạy nhiều lần (không phải mô hình hiện tại).

## Fix

Bọc cleanup trong nhánh except: `shutil.rmtree(ext_dir, ignore_errors=True)` trước khi `return None`. Hoặc dùng context manager/`try/finally` quanh quá trình tạo extension.

## Test

```python
# Mock zipfile.ZipFile raise sau mkdtemp → _create_proxy_auth_extension phải rmtree thư mục tạm, không để sót.
```
