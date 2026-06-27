# Audit Context — nguồn tri thức dùng chung cho mọi pha

> **Mọi agent của workflow audit ĐỌC file này TRƯỚC khi làm việc.** Nó cho biết hệ thống vận hành thế nào, bug nào đã biết, fix nào vừa làm, và quy ước. Maintainer cập nhật file này sau mỗi đợt fix (xem §6).

## 1. Đối tượng & cách đọc code

Hệ Redis + RQ (Redis Queue) crawler phân tán, chạy bằng Docker Compose. Repo root = thư mục làm việc (CWD) của agent.

- Luôn đọc **CODE THẬT** bằng Read/Grep/Bash. **KHÔNG tin line number** trong doc cũ (review trước, bug file) — code đã dịch dòng qua nhiều lần sửa. Tự xác minh line hiện tại bằng Grep.
- Trích dẫn mọi nhận định dạng `file:line`.
- Danh sách bug đầy đủ + trạng thái = chạy `ls Bugs/`. **Filename có `(FIXED)` = đã fix.** Đọc `Bugs/BUG-XX*.md` để biết claim gốc + fix dự kiến.

## 2. File map

| File | Vai trò |
|---|---|
| `redis_server/config.py` | Đọc env: REDIS_HOST/PORT, CRAWLER_NETWORK, PROXY_HOST_DIR (env-only), RESULT_TTL=3600, JOB_TIMEOUT_DEFAULT=120, MEM=1g, SHM=2g, MAX_CONCURRENT_TOTAL=10. `get_max_concurrent(domain)`, `get_job_timeout(domain)`. |
| `redis_server/orchestrator.py` | Discover domain, spawn worker thread, `ThreadSafeWorker(SimpleWorker)` + `TimerDeathPenalty`, crash-recovery `_retry_stale_jobs`. `redis_client` dùng `decode_responses=False`. |
| `redis_server/main.py` | `crawl_job` (RQ task), slot Lua acquire/release, `_set_job_state`/`_clear_job_state`, `_spawn_and_wait_container`. `redis_client` dùng `decode_responses=True`. `docker_client` timeout=240s. |
| `Dashboard/app.py` | Flask API:5000 — submit-job, hiển thị/monitor, clear/stop. `redis_conn` dùng `decode_responses=True`. |
| `workers/{fnac,newark}/run.py` | Entrypoint container: đọc env URL/RET_KEY/PROXY_TYPE/REDIS_*, gọi sourceCode crawl, ghi `result:{ret_key}`. |
| `workers/{fnac,newark}/sourceCode/` | Logic crawl thật (Playwright + proxy). fnac: `HtmlFetchResult.to_dict()`. newark: dict literal. |
| `workers/{manomano,orchestra}/` | **Worker MỚI (06-26/27)** — undetected_chromedriver + Selenium (KHÁC Playwright), Xvfb (entrypoint.sh), Chrome trong-image `/usr/bin/google-chrome`. orchestra ghi thêm `title`/`price`. **Nhiều bug false-success/timeout: BUG-69..76.** |
| `docker-compose.yml`, `start.sh`, `stop.sh`, `setup_systemd.sh` | Orchestration/deploy. compose KHÔNG set project `name:`. |

## 3. Invariant & cơ chế cốt lõi

- **`job_id == ret_key`** ở mọi nơi. ret_key format: `ret_{domain}_{uuid}`.
- **Slot 2 lớp**: `slots:global:total` (max TOTAL) + `slots:domain:{d}` (max per-domain). Lua INCR = hard gate (main.py); `_can_acquire_slots` (orchestrator) = soft pre-check, fail-closed.
- **Concurrency**: mỗi domain spawn `MAX_CONCURRENT_{DOMAIN}` thread, mỗi thread 1 `ThreadSafeWorker` chạy job in-process (không fork).
- **Redis keys**: `job_state:{ret_key}` (TTL 86400, có `retry_count`), `result:{ret_key}` (TTL 3600 thường, **86400 cho give-up**), `slots:*` (3600), `rq:*` (RQ internal, failed=1 năm).
- **Crash-recovery** `_retry_stale_jobs`: re-enqueue job mất, cap `retry_count>=3` → result failed vĩnh viễn. `retry_count` phải được **bảo toàn** qua mọi lần ghi job_state.
- **Phân loại result**: dashboard `status=='success'`→finished, khác→failed (passthrough trung thực field worker ghi).
- **RQ 2.9.1 gotcha**: `Worker.work()` bắt `redis.TimeoutError` và `except:` rồi **`break` + return bình thường** (chỉ `SystemExit` raise). ⟹ Redis blip lúc execute_job KHÔNG raise — code gọi work() phải coi mọi lần return là "cần restart".

## 4. Các fix gần đây (rolling — kiểm regression vào đây trước)

| Bug | Commit | Tóm tắt |
|---|---|---|
| BUG-13 | e921233 | worker tự phục hồi sau Redis blip: slot-wait backoff + restart-on-every-work()-return + delete rq:worker key trước restart |
| BUG-61 | e921233 | delete `rq:worker:{name}` trước restart → tránh register_birth ValueError kẹt ~480s |
| BUG-60 | e921233 | dashboard submit preserve `retry_count` → không reset cap BUG-20 |
| BUG-27 | a34c2d4 | `.env` PROXY_HOST_DIR absolute (đã FIXED) |
| BUG-24 | 451c40f | read-back `setdefault` domain/url/timestamp vào success result |
| BUG-20 | 7507614 | recovery re-enqueue job RQ-failed-no-result + cap retry_count>=3 |
| BUG-49 | 7507614 | fnac: 403/429/503 + http_code==0/>=400 → failed |

## 5. Quy ước

- **Severity**: critical / high / medium / low / nit. Verdict thêm: refuted.
- **Bug mới**: ID kế tiếp = (max trong `ls Bugs/`) + 1. Hiện cao nhất **BUG-80** → mới bắt đầu từ **BUG-81**.
- **Đánh dấu fixed**: đổi tên file `BUG-XX_...md` → `BUG-XX(FIXED)_...md` (git mv) + sửa field `**Status**: FIXED (ngày)` + thêm mục `## Fix Applied`.
- **Result schema** (worker ghi): `{url, html, headers, http_code, cookies, elapsed_ms, error, status}` + (fnac) `ret_key, total_elapsed_seconds, mode, proxy_type, log`. Top-level `domain`/`timestamp` do orchestrator backfill (BUG-24).
- **Dedup finding mới**: so với `ls Bugs/` — nếu trùng claim/file/cơ chế của BUG-XX đã có thì `is_new=false`.

## 6. Bảo trì file này

Sau mỗi đợt fix: (a) thêm dòng vào §4, (b) cập nhật "ID cao nhất" ở §5, (c) nếu cơ chế cốt lõi đổi thì sửa §3. Lịch sử review: `Reviews_Project/2026-06-19`, `2026-06-23`, `2026-06-26`, `2026-06-27` (audit 2 worker mới manomano/orchestra → BUG-69..76).
