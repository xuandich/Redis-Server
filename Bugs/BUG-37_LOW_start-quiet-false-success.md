# BUG-37: start.sh -quiet reports success after fixed 3s sleep without health check

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`-quiet` mode: `docker compose up --no-build > /dev/null 2>&1 &`, sleep cứng 3s, rồi in vô điều kiện "All services started!". Không check redis healthy, orchestrator connected, hay compose có exit ngay (image thiếu cho --no-build, port conflict). Output vứt vào /dev/null → lỗi vô hình.

### Root Cause

[start.sh:161-168](start.sh#L161-L168):
```bash
docker compose up --no-build > /dev/null 2>&1 &
DOCKER_PID=$!         # PID của subshell, không phản ánh health
sleep 3               # cứng
echo "✅ All services started!"   # vô điều kiện
```
Không có `docker compose ps`, redis ping, hay `kill -0 $DOCKER_PID`.

## Impact

- Operator tưởng start thành công khi thực ra fail
- UX/observability, không phải data integrity
- Phần nào được giảm nhẹ bởi bước load/build image ở trên

## Fix

Poll health thay vì sleep cứng:
```bash
docker compose up --no-build -d   # detached, compose tự quản
# Chờ redis healthy
for i in $(seq 1 30); do
    if docker exec redis-server redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "✅ All services started!"; break
    fi
    sleep 1
done
docker compose ps   # show trạng thái thật
```

## Test

```bash
# Xóa 1 image để --no-build fail, rồi:
./start.sh -quiet
# ❌ vẫn in "All services started!" + exit 0
```
