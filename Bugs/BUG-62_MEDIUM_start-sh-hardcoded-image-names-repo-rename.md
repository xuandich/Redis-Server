# BUG-62: start.sh hardcode tên image theo basename thư mục → clone/đổi tên dir là stack không lên

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-26

## Problem

`start.sh:88-89` gọi `load_or_build_image` với tag literal `redis_server-orchestrator:latest` và `redis_server-dashboard:latest`. `docker-compose.yml` **không set** `name:` (project name) cũng không có `COMPOSE_PROJECT_NAME` → Compose suy project name từ **basename thư mục làm việc** và tag image built là `<project>-<service>`. Thư mục hiện tại là `Redis_Server` → lowercase `redis_server` → khớp tag literal HÔM NAY. Nhưng `start.sh` chạy `docker compose up --no-build` ([start.sh:144,147](../start.sh#L144)) — nếu repo được clone/checkout vào thư mục tên khác (vd `crawler`, `Redis-Server`, `app`), Compose tìm image `crawler-orchestrator:latest`… vốn chưa từng build, và `--no-build` cấm build tại chỗ → `docker compose up` abort "image not found".

### Root Cause

- [start.sh:88-89](../start.sh#L88) hardcode `redis_server-*`.
- [docker-compose.yml](../docker-compose.yml) không khai báo `name:` cấp project (dòng `name: crawler-net` là tên network, không phải project).
- `--no-build` ([start.sh:144,147](../start.sh#L144)) chặn fallback build.

> Liên quan đợt move vào `redis_server/` (commit 155be2a): build context là `./redis_server` nhưng project name vẫn lấy từ thư mục NGOÀI.

## Scenario

```
git clone <repo> crawler && cd crawler && ./start.sh
  load_or_build_image build/tag image 'redis_server-orchestrator:latest'
  docker compose up --no-build → Compose tìm 'crawler-orchestrator:latest' (project=crawler)
  → không có → --no-build cấm build → stack không lên
```

## Impact

- Stack không khởi động trên mọi clone/rename thư mục
- Khó chẩn đoán (image build "thành công" nhưng compose tìm tên khác)

## Fix

Khai báo project name cố định trong `docker-compose.yml`:
```yaml
name: redis_server
```
hoặc set `COMPOSE_PROJECT_NAME=redis_server` trong `.env`/`start.sh`, để tag image độc lập với tên thư mục.

## Test

```bash
cp -r Redis_Server /tmp/crawler && cd /tmp/crawler && ./start.sh
docker compose ps   # ✅ sau fix: orchestrator+dashboard up bất kể tên thư mục
```
