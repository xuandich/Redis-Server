# BUG-32: _release_slot SET(key,0) strips the slot key's TTL

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

Lua acquire set `EXPIRE 3600` mỗi lần (main.py:23). Release path corrective `redis_client.set(redis_key, 0)` (main.py:51) ghi không kèm `KEEPTTL` → **xóa expiry**, để lại slot key persistent (TTL -1). Cosmetic — value=0 không chặn acquire, self-heal khi acquire kế tiếp set lại EXPIRE, và `cleanup_stale_workers` wipe `slots:*` lúc restart.

### Root Cause

[main.py:46-51](main.py#L46-L51):
```python
def _release_slot(slot_type: str, key: str):
    val = redis_client.decr(redis_key)
    if val < 0:
        redis_client.set(redis_key, 0)   # ← SET không KEEPTTL → xóa TTL
```
Redis `SET` không có `KEEPTTL` sẽ clear TTL hiện có → key thành persistent. Chỉ trigger ở nhánh bất thường (double/over-release).

## Impact

- Cosmetic TTL-hygiene: key value=0 có thể tồn tại tới acquire kế tiếp hoặc restart
- Không leak slot, không chặn acquire (Lua check `current < max` pass khi =0)

## Fix

```python
redis_client.set(redis_key, 0, keepttl=True)   # hoặc ex=3600
```

## Test

```bash
# Force nhánh âm (double release), rồi:
redis-cli TTL slots:global:total
# ❌ -1  →  ✅ <=3600
```
