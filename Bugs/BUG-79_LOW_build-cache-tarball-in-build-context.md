# BUG-79: Cache image .tar.gz (~421MB) nằm TRONG build context → ship 402MB context mỗi lần build worker

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-27

## Problem

`start.sh` build worker: `docker build -t "$image_name" "$worker_dir"` ([start.sh:109,118](../start.sh#L109)) với build context = chính thư mục worker. Sau build: `docker save "$image_name" | gzip > "$cache_file"` ([start.sh:111,120](../start.sh#L111)) ghi vào `cache_file="${worker_dir}worker-${domain}-latest.tar.gz"` ([start.sh:99](../start.sh#L99)) — **ngay TRONG build context**.

**Không có `.dockerignore`** nào trong repo → Docker tar + gửi TOÀN BỘ context (gồm tar.gz 421MB) cho daemon mỗi lần build. Đo thực: `du -sh workers/manomano` = **402M** / `workers/orchestra` = **402M** vs `workers/fnac` = 124K — toàn bộ chênh là file tar.gz. Dockerfile dùng COPY chọn lọc nên tar.gz KHÔNG vào image, nhưng chi phí transfer context vẫn xảy ra.

## Impact (LOW)

- Build worker manomano/orchestra phải tar + gửi ~402MB context cho daemon (I/O cục bộ, không phải network) → chậm + churn disk. Vòng lặp: mỗi build ghi tar.gz mới → context non-deterministic.
- **Bounded**: chỉ chạy ở cold-build / cache-load-fail ([start.sh:101](../start.sh#L101) `docker image inspect` short-circuit khi image đã có), KHÔNG phải mỗi lần `start.sh`. Không lỗi correctness — chỉ build-time perf + deploy hygiene.
- Worker đầu tiên có image nặng cache vào build dir → fnac/newark chưa lộ (chưa có tar.gz).
- Khác BUG-34 (race `docker load` cùng tar.gz lúc runtime), BUG-40/62/76.

## Fix

Thêm `workers/*/.dockerignore` chứa `*.tar.gz` (tối thiểu); HOẶC đặt cache file ngoài build context — vd `Redis_Docker_Image/` như image orchestrator/dashboard ([start.sh:55](../start.sh#L55)).
