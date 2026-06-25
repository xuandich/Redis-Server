# BUG-36: stop.sh -clear prints "Redis cleared!" even when redis-cli missing / FLUSHALL failed

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

Path `-clear` phụ thuộc redis-cli host nói chuyện `localhost:$REDIS_PORT`. Nếu thiếu redis-tools → skip clear (lines 33-35) NHƯNG script vẫn in "All services stopped and Redis cleared!" (line 52) — false success. FLUSHALL fail cũng bị nuốt bởi `> /dev/null 2>&1`.

### Root Cause

[stop.sh:26-36](stop.sh#L26-L36):
```bash
if command -v redis-cli &> /dev/null; then
    redis-cli -p $REDIS_PORT FLUSHALL > /dev/null 2>&1   # lỗi bị nuốt
    ...
else
    echo "  ⚠️  redis-cli not found, skipping Redis cleanup"
fi
```
[stop.sh:51-52](stop.sh#L51-L52) in "Redis cleared!" vô điều kiện khi `CLEAR_JOBS=true`, bất kể có clear thật hay không.

## Impact

- Operator tưởng đã wipe data nhưng data còn trong volume redis-data
- Chỉ teardown script, không phải data path; lỗi có warning ở line 31/34

## Fix

Clear qua container (luôn có redis-cli) + báo theo kết quả thật:
```bash
if docker exec redis-server redis-cli FLUSHALL > /dev/null 2>&1; then
    echo "  ✅ Redis data cleared"
    CLEARED=true
else
    echo "  ⚠️  Could not clear Redis"
    CLEARED=false
fi
...
[ "$CLEARED" = true ] && echo "...Redis cleared!" || echo "...stopped (Redis NOT cleared)"
```

## Test

```bash
# Trên host không có redis-tools:
./stop.sh -clear
# ❌ in "Redis cleared!" dù không clear
```
