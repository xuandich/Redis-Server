# BUG-45: `config.py` có constants định nghĩa nhưng không được dùng — thay đổi không có tác dụng

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-22

## Problem

`config.py` định nghĩa một số constants mà không có code nào trong project thực sự đọc chúng. Nếu ai sửa các constants này nghĩ là thay đổi behavior → không có tác dụng gì → silent misconfiguration.

## Root Cause

[config.py:36-51](config.py#L36):

```python
# Các constants này được ĐỊNH NGHĨA nhưng KHÔNG ĐƯỢC DÙNG bởi bất kỳ logic nào:

MAX_CONCURRENT_FNAC = int(os.environ.get('MAX_CONCURRENT_FNAC', 5))   # ← unused
MAX_CONCURRENT_AMAZON = int(os.environ.get('MAX_CONCURRENT_AMAZON', 3))  # ← unused

MAX_RETRIES = int(os.environ.get('MAX_RETRIES', 3))  # ← unused, no retry logic

QUEUE_FNAC = 'crawler:fnac'      # ← unused, queue name hardcoded inline
QUEUE_AMAZON = 'crawler:amazon'  # ← unused
QUEUE_NEWARK = 'crawler:newark'  # ← unused
```

Logic thực tế dùng `get_max_concurrent(domain)` đọc thẳng từ env:
```python
def get_max_concurrent(domain: str) -> int:
    return int(os.environ.get(f'MAX_CONCURRENT_{domain.upper()}', 5))
```

Sửa `MAX_CONCURRENT_FNAC = 3` trong config.py → `get_max_concurrent('fnac')` vẫn đọc `os.environ.get('MAX_CONCURRENT_FNAC', 5)` = 5 (từ .env) → không đổi gì.

## Impact

- **Misleading maintenance trap**: developer thay đổi constant nghĩ là override → không có tác dụng
- `MAX_RETRIES=3` đặc biệt nguy hiểm — không có retry logic trong code nhưng constant tồn tại, có thể khiến devs tìm bug retry "sao không retry?"
- `QUEUE_*` constants gợi ý hardcoded domain list nhưng system thực tế auto-discover từ `workers/`

## Fix

Xóa các unused constants, chỉ giữ lại nếu thực sự được import/dùng ở nơi khác:

```python
# Xóa:
# MAX_CONCURRENT_FNAC = ...
# MAX_CONCURRENT_AMAZON = ...
# MAX_RETRIES = ...
# QUEUE_FNAC = ...
# QUEUE_AMAZON = ...
# QUEUE_NEWARK = ...
```

Hoặc thêm comment rõ ràng:
```python
# NOTE: các hằng số dưới đây chỉ để documentation — logic thực dùng get_max_concurrent()
# Thay đổi ở đây KHÔNG có tác dụng — phải sửa trong .env
MAX_CONCURRENT_FNAC = int(os.environ.get('MAX_CONCURRENT_FNAC', 5))
```
