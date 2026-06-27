# BUG-75: .env.example thiếu MAX_CONCURRENT_MANOMANO/ORCHESTRA → fresh deploy spawn 5 thread/domain thay vì 3

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-27

## Problem

`.env` thật bị gitignore (`git check-ignore .env` → exit 0; chỉ `.env.example` được track). Fresh clone phải `cp .env.example .env`. Nhưng `.env.example` **thiếu** `MAX_CONCURRENT_MANOMANO` và `MAX_CONCURRENT_ORCHESTRA` (chỉ có FNAC/AMAZON/NEWARK). `.env` thật có cả hai = 3.

`discover_worker_domains` ([orchestrator.py:88-94](../redis_server/orchestrator.py#L88)) tìm thấy manomano + orchestra (dir có Dockerfile) → spawn `get_max_concurrent(domain)` thread ([orchestrator.py:304](../redis_server/orchestrator.py#L304)). `get_max_concurrent` fallback **5** khi thiếu env ([config.py:41](../redis_server/config.py#L41)).

→ Deploy theo example: manomano + orchestra spawn **5 thread/domain thay vì 3**.

> Cùng họ BUG-66 (.env.example thiếu PROXY_HOST_DIR) nhưng khác field cụ thể (concurrency). Lưu ý: phần claim ban đầu về NEWARK/JOB_TIMEOUT đã bị bác — `.env.example` CÓ `MAX_CONCURRENT_NEWARK=3` + `JOB_TIMEOUT_NEWARK=720`; JOB_TIMEOUT manomano/orchestra thiếu ở CẢ HAI file (xem BUG-74).

## Impact

- Over-spawn thread cho 2 domain mới khi deploy từ example.
- **Nhỏ**: bị cắt bởi `MAX_CONCURRENT_TOTAL=10` (Lua hard gate, [main.py:93](../redis_server/main.py#L93)) → thread dư phần lớn idle chờ slot, không overcommit thật. Chỉ tốn thread/RAM nhẹ.

## Fix

Thêm vào `.env.example`:
```
MAX_CONCURRENT_MANOMANO=3
MAX_CONCURRENT_ORCHESTRA=3
JOB_TIMEOUT_MANOMANO=720
JOB_TIMEOUT_ORCHESTRA=720
```
(2 dòng JOB_TIMEOUT gắn với fix BUG-74). Lý tưởng: `.env.example` đồng bộ mọi key `.env` thật dùng.
