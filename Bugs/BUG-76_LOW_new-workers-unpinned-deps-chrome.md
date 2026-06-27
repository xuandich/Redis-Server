# BUG-76: manomano/orchestra — deps + google-chrome-stable không pin version → build không tái lập

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-27

## Problem

`workers/{manomano,orchestra}/sourceCode/requirements.txt` toàn `>=`, không cận trên, không lockfile:
```
undetected-chromedriver>=3.5.0
selenium>=4.0.0
redis>=4.0.0
pandas>=2.0.0
openpyxl>=3.1.0
```
Dockerfile cài `google-chrome-stable` cũng **không pin** ([Dockerfile:14-15](../workers/manomano/Dockerfile#L14)) và CÓ `pip install -r requirements.txt` (deps sống, không chết).

Hai moving target ghép nhau: rebuild kéo Chrome stable mới nhất + uc/selenium mới nhất. `predownload_driver.py` đọc `google-chrome --version` rồi `uc.Chrome(version_main=ver)` ([predownload_driver.py:5,14](../workers/manomano/predownload_driver.py#L5)) → uc phải tải chromedriver khớp Chrome major. Nếu uc lag sau Chrome major mới → mismatch.

> Cùng lớp "unpinned-dep" với BUG-54 (orchestrator image) nhưng khác file + khác hậu quả → bug riêng.

## Impact

- **Build không tái lập**: 2 lần build cùng source → image khác nhau, làm hỏng ý nghĩa cache `worker-<domain>-latest.tar.gz` ([start.sh:99](../start.sh#L99)).
- Mismatch Chrome/uc **fail lúc `docker build`** (predownload chạy tại build-time, [Dockerfile:26](../workers/manomano/Dockerfile#L26)) — fail to + sớm, KHÔNG fail âm thầm per-fetch lúc runtime. → severity LOW (build hygiene, không phải lỗi runtime hiện hữu).

## Fix

Pin version trong requirements.txt (vd `undetected-chromedriver==3.5.5`, `selenium==4.x.y`) + pin `google-chrome-stable=<ver>` trong Dockerfile, hoặc dùng lockfile (uv/pip-tools). Đồng bộ với hướng fix BUG-54.
