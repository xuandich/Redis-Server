# BUG-27: PROXY_HOST_DIR is a relative path — breaks proxy mount on direct 'docker compose up'

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`.env` đặt `PROXY_HOST_DIR=./workers/Proxy` (relative). Docker daemon resolve host bind-mount source theo daemon root (`/`), **không** theo cwd của orchestrator → relative path fail hoặc mount sai thư mục. `start.sh` override bằng absolute path nên **bị che** — ai chạy `docker compose up` trực tiếp (path compose-native, có ghi trong README) thì proxy mount hỏng.

### Root Cause

1. [.env:7](.env#L7) — `PROXY_HOST_DIR=./workers/Proxy` (relative).

2. [docker-compose.yml:35](docker-compose.yml#L35) — `PROXY_HOST_DIR: ${PROXY_HOST_DIR}` truyền verbatim vào orchestrator container.

3. [main.py:130-132](main.py#L130-L132) — dùng làm **host-side** source của bind mount:
```python
if PROXY_HOST_DIR:
    volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}
```
Docker daemon (qua socket) cần absolute host path — relative `./workers/Proxy` không resolve được theo cwd container.

4. [start.sh:146](start.sh#L146) — `export PROXY_HOST_DIR="$PROXY_DIR"` (absolute, từ `$PROJECT_ROOT`) override .env **chỉ khi chạy qua start.sh**.

## Scenario

```
Chạy `docker compose up` trực tiếp (không qua start.sh)
  → PROXY_HOST_DIR = './workers/Proxy' (từ .env)
  → main.py spawn worker với bind mount source './workers/Proxy'
  → dockerd không resolve được relative path theo root '/'
  → /app/Proxy trong worker thiếu/sai
  → worker đọc proxy list fail
```

## Impact

- Proxy mount hỏng khi không dùng start.sh
- Bị che trong flow bình thường → khó phát hiện
- README có hướng dẫn compose-native → user dễ dính

## Fix

Đổi `.env` sang absolute path, hoặc tốt hơn — resolve trong code/compose. Đơn giản nhất:
```ini
# .env — dùng absolute path
PROXY_HOST_DIR=/home/xuandich/CODE/PO/Redis_Server/workers/Proxy
```
Hoặc trong main.py, resolve relative → absolute dựa trên một ENV gốc đã biết. Hoặc document rõ "phải chạy qua start.sh".

## Test

```bash
# Chạy trực tiếp KHÔNG qua start.sh
docker compose up -d
# Submit job cần proxy
python test_api_job.py "https://www.fnac.com/x" "fnac"
docker exec <worker> ls /app/Proxy
# ❌ thiếu/sai
# ✅ sau fix: có buyproxies_List.xlsx
```
