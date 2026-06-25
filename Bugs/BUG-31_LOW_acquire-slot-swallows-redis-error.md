# BUG-31: _acquire_slot swallows Redis errors → job mislabeled 'slot timeout'

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`_acquire_slot` bọc Lua call trong try/except, bất kỳ Exception nào → print + return False (fail-closed). Caller `crawl_job` không phân biệt được "thật sự full 60s" với "Redis lỗi ngay lần đầu". Redis blip tạm thời → job báo ngay "Global/Domain slot timeout" + ghi result failed, dù chưa hề có slot contention. Lỗi thật (e) chỉ print, không vào result → client nhận thông báo sai lệch.

### Root Cause

[main.py:39-41](main.py#L39-L41):
```python
except Exception as e:
    print(f"[ERROR] Slot acquire failed: {e}", flush=True)
    return False    # ← return ngay, không phân biệt lỗi vs full
```
Caller [main.py:77-82](main.py#L77-L82) coi `False` = timeout → ghi `{'error': 'Global slot timeout'}`.

## Impact

- Lỗi hạ tầng bị gán nhãn "slot timeout" → chẩn đoán sai
- Fail-closed nên an toàn về slot integrity, chỉ sai diagnostics
- Window hẹp (Lua raise nhưng setex sau đó thành công)

## Fix

Phân biệt lỗi Redis vs full — raise/đánh dấu riêng:
```python
except Exception as e:
    print(f"[ERROR] Slot acquire failed: {e}", flush=True)
    raise   # để crawl_job ghi error rõ ràng (infra error), hoặc trả mã lỗi riêng
```
(Cân nhắc cùng BUG-13 — fragility chung của Redis error handling.)

## Test

```bash
# Inject Redis error ngay lần acquire đầu → job phải báo lỗi infra, không 'slot timeout'
```
