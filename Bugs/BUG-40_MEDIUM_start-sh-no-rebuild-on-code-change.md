# BUG-40: start.sh không rebuild image khi source code thay đổi

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-22

## Problem

`start.sh` kiểm tra image tồn tại bằng `docker image inspect` — nếu image đã có trong system thì skip build hoàn toàn, **không quan tâm source code có thay đổi hay không**. Sau khi sửa `app.py`, `main.py`, `orchestrator.py` hoặc bất kỳ file nào trong image, phải rebuild thủ công — nếu không container vẫn chạy code cũ mà không có warning nào.

### Root Cause

[start.sh:63-96](start.sh#L63-L96) — `load_or_build_image`:
```bash
if docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "✅ $IMAGE_NAME already in system"
    return 0    # ← skip hoàn toàn, không so sánh mtime
fi
```

Không có:
- So sánh timestamp build vs mtime của source files
- Content hash check
- `docker image inspect .RepoDigests` vs build context hash

### Scenario

```
Sửa Dashboard/app.py (fix domain extraction bug)
./start.sh -quiet
  → "✅ redis_server-dashboard:latest already in system"
  → docker compose up --no-build (không build)
Dashboard container chạy code cũ → bug còn nguyên
User không biết image stale, debug sai hướng
```

Đây là lỗi đã xảy ra thực tế 2026-06-22: dashboard image build 19/6, app.py sửa 22/6, start.sh không rebuild → domain vẫn bị extract sai.

## Impact

- Code fix không có tác dụng cho đến khi rebuild thủ công
- Không có warning, operator không biết image stale
- Đặc biệt nguy hiểm sau nhiều session sửa code

## Fix

Thêm bước rebuild force khi detect source mới hơn image:
```bash
# Trong load_or_build_image — sau khi image inspect thành công
IMAGE_CREATED=$(docker image inspect "$IMAGE_NAME" --format '{{.Created}}' 2>/dev/null)
IMAGE_TS=$(date -d "$IMAGE_CREATED" +%s 2>/dev/null || echo 0)

# So sánh với mtime của build context
BUILD_CTX="$PROJECT_ROOT"
if [ "$SERVICE_NAME" = "dashboard" ]; then BUILD_CTX="$PROJECT_ROOT/Dashboard"; fi
NEWEST_SRC=$(find "$BUILD_CTX" -name "*.py" -newer /dev/null -printf '%T@\n' 2>/dev/null | sort -n | tail -1 | cut -d. -f1)
NEWEST_SRC=${NEWEST_SRC:-0}

if [ "$NEWEST_SRC" -gt "$IMAGE_TS" ]; then
    echo "⚠️  $IMAGE_NAME stale (source newer) — rebuilding..."
    docker compose build "$SERVICE_NAME" > /dev/null 2>&1 && echo "   ✅ Rebuilt"
fi
```

Hoặc đơn giản hơn: thêm flag `-force-rebuild` để manual trigger khi cần.

## Test

```bash
# Sửa 1 file py trong Dashboard/
touch Dashboard/app.py
./start.sh -quiet
# ❌ hiện tại: "✅ already in system" — không rebuild
# ✅ sau fix: detect source mới hơn, tự rebuild
```
