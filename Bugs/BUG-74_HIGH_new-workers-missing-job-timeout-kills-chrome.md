# BUG-74: manomano/orchestra thiếu JOB_TIMEOUT riêng → container.wait(120s) giết Chrome giữa chừng

**Severity**: HIGH
**Status**: OPEN
**Date**: 2026-06-26

## Problem

`_spawn_and_wait_container` chờ container bằng `container.wait(timeout=get_job_timeout(domain))` ([main.py:181](../redis_server/main.py#L181)). `get_job_timeout` fallback `JOB_TIMEOUT_DEFAULT=120` khi không có `JOB_TIMEOUT_{DOMAIN}` ([config.py:45](../redis_server/config.py#L45)). `.env` có `JOB_TIMEOUT_NEWARK=720` nhưng **KHÔNG có `JOB_TIMEOUT_MANOMANO`/`JOB_TIMEOUT_ORCHESTRA`** → cả hai dùng **120s**.

Nhưng 2 worker mới (undetected_chromedriver + chờ Cloudflare) chậm hơn nhiều:
- manomano `_navigate_and_get_html`: `sleep(3-5)` + CF wait loop **18 vòng × 5s = 90s** ([extractor.py:163-179](../workers/manomano/sourceCode/extractor.py#L163)) + `WebDriverWait(20)` ([extractor.py:183](../workers/manomano/sourceCode/extractor.py#L183)) ≈ **~115s/attempt**, và `_fetch_sync` chạy tới **3 attempts** (proxy + fallback direct).
- orchestra: CF wait + render tương tự (extractor.py:191-202).

→ Một job manomano/orchestra gặp CF challenge (chính là lý do dùng undetected_chromedriver) **thường xuyên vượt 120s** ngay ở 1 attempt.

## Scenario

```
container.wait(timeout=120)  (manomano)
  → job CF-challenge cần ~115s/attempt × (tới 3 attempt) >> 120s
  → container.wait raise (main.py:183)
  → container.kill() (main.py:186) → Chrome bị giết GIỮA CHỪNG
  → ghi result status='failed' "Container timeout/error" (main.py:189-194)
  → crash-recovery có thể re-enqueue → lặp lại → tốn tài nguyên, fail hệ thống
```

## Impact

- **Phần lớn job manomano/orchestra chậm (CF) bị giết oan ở 120s** → false-failure hàng loạt + retry lãng phí (mỗi retry lại spawn Chrome nặng).
- newark đã được cấp 720s đúng vì lý do này; 2 worker mới **chậm hơn** lại bị bỏ sót → regression cấu hình rõ ràng.

## Fix

Thêm vào `.env` (và `.env.example`):
```
JOB_TIMEOUT_MANOMANO=720
JOB_TIMEOUT_ORCHESTRA=720
```
(hoặc giá trị ≥ worst-case: ~3 × 115s + overhead spawn ≈ 400s, nên 600-720s an toàn). Cân nhắc nâng `docker_client` timeout ([main.py:15](../redis_server/main.py#L15)) tương ứng (hiện `JOB_TIMEOUT_DEFAULT + 120`).

## Test

```
Submit job manomano gặp CF challenge (cần >120s) → KHÔNG bị kill ở 120s, chạy đến khi xong/đủ retry.
```
