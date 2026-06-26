# BUG-66: .env.example thiếu PROXY_HOST_DIR → cp .env.example .env tắt proxy mounting âm thầm

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-26

## Problem

`.env` bị gitignore (`git check-ignore .env` → 0); `.env.example` là template env DUY NHẤT được track. Fresh clone không có `.env` → người dùng tạo từ `.env.example`. Nhưng `.env.example` **KHÔNG có dòng `PROXY_HOST_DIR`** (`.env` thật thì có, absolute path). Sau khi BUG-27 làm `.env` thành nguồn duy nhất, không còn fallback nào cứu.

### Root Cause (chuỗi đã xác minh)

1. `cp .env.example .env` → `PROXY_HOST_DIR` không tồn tại.
2. [start.sh:9](../start.sh#L9) `export $(grep -v '^#' .env | xargs)` chỉ export var có trong `.env` → `PROXY_HOST_DIR` unset.
3. [start.sh:27-30](../start.sh#L27) `if [ ! -d "$PROXY_HOST_DIR" ]` với biến rỗng = `[ ! -d "" ]` = true → CHỈ in warning "run without proxy", **KHÔNG exit**.
4. [docker-compose.yml:35](../docker-compose.yml#L35) `PROXY_HOST_DIR: ${PROXY_HOST_DIR}` nội suy rỗng vào orchestrator.
5. [config.py:18](../redis_server/config.py#L18) `os.environ.get('PROXY_HOST_DIR','')` → `''`.
6. [main.py:154](../redis_server/main.py#L154) `if proxy_type=='standard' and PROXY_HOST_DIR and isdir(...)` → `''` falsy → rớt sang elif (156-158) → `proxy_type='none'`, volume proxy KHÔNG bao giờ mount.

> Tăng nặng: block `.env` mẫu trong README (dòng ~88-99) CŨNG thiếu `PROXY_HOST_DIR` → tạo `.env` thủ công theo doc cũng hỏng.
> Khác BUG-27 (giá trị relative HIỆN DIỆN nhưng sai) — đây là **thiếu hẳn** trong template. Đã được ghi "còn sót" trong BUG-27(FIXED) nhưng chưa có file riêng.

## Scenario

```
Fresh clone → cp .env.example .env → ./start.sh
  → PROXY_HOST_DIR rỗng → warning "run without proxy" (không sập)
  → MỌI job proxy_type='standard' chạy KHÔNG proxy → dễ 403/block
```

## Impact

- Lần setup đầu: mọi standard job chạy không proxy, chỉ có log warning, không crash → rất khó phát hiện.

## Fix

Thêm vào `.env.example` (kèm chú thích bắt buộc sửa):
```ini
# Host path tuyệt đối tới thư mục Proxy (BẮT BUỘC cho proxy_type=standard)
PROXY_HOST_DIR=/đường/dẫn/tuyệt/đối/tới/workers/Proxy
```
Đồng bộ block `.env` mẫu trong README. Cân nhắc cho start.sh **hard-fail** (hoặc cảnh báo rõ) khi `proxy_type` mặc định 'standard' mà `PROXY_HOST_DIR` rỗng.

## Test

```bash
cp .env.example .env   # không sửa
./start.sh
docker exec orchestrator python -c "import os;print(repr(os.environ.get('PROXY_HOST_DIR')))"
# ❌ hiện tại: '' → proxy tắt; ✅ sau fix: .env.example có dòng PROXY_HOST_DIR rõ ràng
```
