# Code Review — Flow Audit (2026-06-23)

**Commit**: `42858d5` (branch `main`) — "Refactor: move orchestrator files into redis_server/"
**Phương pháp**: Workflow audit đối kháng — 8 dimension fan-out → adversarial verify (real? + dedup vs 47 bug đã ghi) → synthesis. **29 agents, 20 raw findings → 12 confirmed (BUG-48→59), 8 refuted/duplicate.**
**Phạm vi**: redis_server/{config,main,orchestrator}.py, Dashboard/app.py, workers/{fnac,newark}/{run.py, sourceCode/}, docker-compose.yml, .env, start.sh, stop.sh, Dockerfiles, pyproject.toml. **Mở rộng so với 06-19**: thêm newark worker + tác động của đợt move file.

> File này nối tiếp [2026-06-19_flow-audit.md](2026-06-19_flow-audit.md). Nó ghi **delta** trạng thái + **finding mới**, và đối chiếu checklist lần trước. Snapshot để lần sau so tiếp.

---

## 1. Đối chiếu checklist 2026-06-19 (mục 5 của file cũ)

| Checklist cũ | Kết quả đối chiếu hôm nay |
|---|---|
| **BUG-13 → BUG-38 đã fix chưa?** | **Hầu như chưa.** Chỉ **BUG-15** được fix (`(FIXED)` trong filename). BUG-13, 16–38 vẫn OPEN. **BUG-14**: code đã fix session này ([redis_server/main.py](../redis_server/main.py) — ghi result + clear state khi thiếu image) nhưng **file chưa rename** `(FIXED)`. |
| **Có bug mới phát sinh từ các fix không?** | **Có — từ đợt refactor, không phải từ fix logic.** Việc move file vào `redis_server/` sinh **BUG-59** (discover_worker_domains phân giải `workers/` sai khi chạy local). Ngoài ra `.env` đã bỏ `PROXY_HOST_DIR` (xem mục 2). |
| **Finding mục 4 (đã bác bỏ) còn đúng không-phải-bug?** | **Còn đúng.** Logic ở các vùng đó không đổi. Lưu ý: một số "không-phải-bug" cũ nay có biến thể THẬT đã tách riêng — vd "container.wait + socket timeout 240s" giờ là **BUG-41** (timeout cứng không theo JOB_TIMEOUT_NEWARK=720). |
| **Worker domain mới (ngoài fnac) tuân thủ result schema?** | **KHÔNG đầy đủ.** newark đã thêm nhưng: thiếu `domain`/`timestamp` top-level (BUG-24/25 áp dụng cả newark), và có nhiều nhánh `http_code: 0` → **BUG-53** (success với http_code=0). Còn **BUG-52** (browser leak) + **BUG-58** (page đã đóng) riêng của newark. |
| **Chạy lại workflow audit, so confirmed count (29)?** | Lần này **12 confirmed** / 20 raw. Thấp hơn 06-19 (29/48) vì bề mặt bug "dễ" đã được ghi nhận; finding mới đòi đào sâu hơn (newark sourceCode, async death-penalty, double-prefix RQ key, đợt move file). |

---

## 2. Delta trạng thái bug từ 2026-06-19

**Tại review 06-19**: mở BUG-13→38 (26 bug). **Hôm nay**: 59 bug tổng, **16 FIXED / 43 OPEN**.

### Đã FIX kể từ 06-19
- **BUG-15** (containers.run không bọc try) — đã fix.
- **BUG-42** (proxy-mount-ignores-proxy-type), **BUG-43** (dashboard-html-null-drops-results), **BUG-47** (proxy-check-host-path-inside-container) — phát hiện **và** fix sau review.
- **BUG-14** — code fix session này, *file chưa đánh dấu `(FIXED)`* ⚠️.

### Bug MỚI phát sinh sau 06-19, vẫn OPEN
- **BUG-39** (ret-key-short-misleading), **BUG-40** (start-sh-no-rebuild), **BUG-41** (docker-client-timeout-fixed), **BUG-44** (job-state-not-cleared-basexception), **BUG-45** (config-dead-constants), **BUG-46** (env-dead-amazon-config).

### Thay đổi bối cảnh đáng chú ý (ảnh hưởng bug cũ)
- **`.env` đã BỎ `PROXY_HOST_DIR`** (review 06-19 cite `.env:7`). Nay biến chỉ được `start.sh` export (absolute, runtime). ⟹ `docker compose up` trực tiếp (không qua start.sh) ⟹ `${PROXY_HOST_DIR}` rỗng ⟹ proxy tắt cho mọi job. **BUG-27** vẫn còn nhưng cơ chế đã dịch: không còn là "relative path" mà là "không có default trong .env". Cần cập nhật mô tả BUG-27.

---

## 3. Tác động đợt move file vào `redis_server/` (commit 42858d5)

> **Mô hình worker KHÔNG đổi so với 06-19.** Vẫn là `class ThreadSafeWorker(SimpleWorker)` ([redis_server/orchestrator.py:42](../redis_server/orchestrator.py#L42)) với `death_penalty_class = TimerDeathPenalty`, chạy job **in-process (không fork)**, mỗi domain spawn `MAX_CONCURRENT_{DOMAIN}` thread, mỗi thread 1 instance xử lý 1 job. ⟹ Toàn bộ **§1.5 (Concurrency model)** và **§1.6 (Crash recovery)** của bản 06-19 **vẫn còn hiệu lực nguyên vẹn** — chỉ đổi tiền tố thư mục path. Thay đổi cấu trúc DUY NHẤT giữa 2 lần review là **đợt move file**, không phải đổi kiến trúc worker/queue.

> Flow map mục 1 của file 06-19 dùng path **gốc root** (`main.py`, `orchestrator.py`, `config.py`). Sau move, các path đó là **`redis_server/main.py`** v.v. File:line logic **không đổi** (chỉ đổi thư mục), nên các tham chiếu trong `Bugs/` cũ vẫn đúng dòng, chỉ lệch tiền tố thư mục. **Bản đồ flow đầy đủ, line đã cập nhật cho commit này, xem §8.**

| Khía cạnh | Trạng thái sau move |
|---|---|
| `docker-compose.yml` build context | ✅ đã đổi `build: ./redis_server` |
| Dockerfile `COPY config.py main.py orchestrator.py` | ✅ đúng — cùng thư mục build context |
| `workers/` volume mount → `/app/workers` | ✅ đúng trong container (WORKDIR `/app`) |
| `Path(__file__).parent / 'workers'` (orchestrator.py:71) | ⚠️ **BUG-59** — trong container OK (`/app/workers`), nhưng chạy LOCAL từ `redis_server/` → `redis_server/workers` (không tồn tại) → 0 domain |
| `cache_file = f'workers/{domain}/...'` (main.py) relative CWD | ✅ trong container CWD=`/app` OK; local thì phụ thuộc CWD |

---

## 4. Finding MỚI lần này (BUG-48 → BUG-59)

12 bug, đã adversarially-verify (đọc lại code thật để bác bỏ) + dedup vs 47 bug cũ.

| ID | Sev | Tóm tắt | File |
|---|---|---|---|
| **BUG-48** | **MED-HIGH** | `clear_state('queued')` truyền full RQ key vào `Queue()` → double-prefix `rq:queue:rq:queue:...` → job queued thật **không bị xóa**, báo "deleted" giả | Dashboard/app.py:609-617 |
| **BUG-49** | **MED-HIGH** | fnac: trang lỗi non-403 (404/429/500/502/503) + response null bị ghi `status='success'` | workers/fnac/sourceCode/extractor.py |
| BUG-50 | MED | `CHROMIUM_SNAP_DIR` bind-mount vô điều kiện, không check tồn tại → APIError mọi job trên host thiếu snap | redis_server/main.py:137 |
| BUG-51 | MED | `submit-job` route theo prefix `ret_key` client gửi, không theo URL thật → worker sai crawl site sai | Dashboard/app.py:789-828 |
| BUG-52 | MED | newark: browser/context/page + playwright leak mỗi lần (re)start → Chromium mồ côi tích tụ → OOM-kill container | workers/newark/sourceCode/extractor.py |
| BUG-53 | MED | newark: result `success` với `http_code=0` (GraphQL listener không fire) → che block/captcha | workers/newark/sourceCode/extractor.py |
| BUG-54 | MED | Orchestrator Dockerfile bỏ qua `requirements.txt`, `pip install` redis/rq/docker **không pin** → nguy cơ lệch version RQ với Dashboard | redis_server/Dockerfile:5 |
| BUG-55 | LOW | Slot leak khi `TimerDeathPenalty` bắn async vào khe hở giữa INCR và `try/finally` (đặc biệt quanh `_set_job_state`) | redis_server/main.py:77-115 |
| BUG-56 | LOW | SCAN aggregation thiếu dedup (`get_stats`/`get_jobs_by_state`/`clear_*`) → thổi phồng số liệu khi Redis rehash trả key trùng | Dashboard/app.py |
| BUG-57 | LOW | `get_jobs_by_state`: page ≤ 0 → slicing âm → cửa sổ kết quả sai/rỗng (bổ sung BUG-28 về int parse) | Dashboard/app.py:78 |
| BUG-58 | LOW | newark: thao tác trên page đã đóng/None sau restart fail → exception giả, che lỗi gốc | workers/newark/sourceCode/extractor.py |
| BUG-59 | LOW | `discover_worker_domains()` phân giải `workers/` tương đối với `redis_server/` sau move → 0 domain khi chạy ngoài `/app` | redis_server/orchestrator.py:71 |

**Chủ đề nổi bật**: (1) trang lỗi/block bị gắn nhãn `success` ở cả 2 worker (BUG-49, 53) — nguy hiểm nhất vì âm thầm; (2) mount/path hard-code dễ vỡ sau move file & đổi host (BUG-50, 59); (3) endpoint dashboard báo thành công giả (BUG-48, 57); (4) rò rỉ tài nguyên tích lũy theo vòng đời tiến trình (BUG-52, 55).

---

## 5. Đã ADVERSARIALLY BÁC BỎ lần này — đừng flag lại

Đã đọc code thật, xác nhận **KHÔNG phải bug mới** (trùng bug cũ hoặc finder misread):
- **"Job timeout budget bị slot-wait ăn → death penalty fire sớm"** → trùng **BUG-17** (toctou-slot-precheck-race).
- **"Worker threads busy-poll 1s vô tận khi slot saturated"** → trùng/misread **can-acquire-slots-fail-open** (đã fix); gate là đúng thiết kế, không spin sai.
- **"images.load() chạy dưới socket timeout 240s"** → trùng **BUG-41** (docker-client-timeout-fixed-to-default).
- **"Crash-recovery re-enqueue dùng positional args làm hỏng dashboard url"** → misread: `q.enqueue(crawl_job, url, domain, ret_key, proxy_type, ...)` truyền đúng thứ tự tham số `crawl_job`; dashboard đọc `job_state` chứ không đọc RQ job args.
- **"Worker Redis client không có socket timeout → container treo"** → trùng họ **runpy-result-write-outside-try** (BUG-22); container vẫn bị `container.wait(timeout)` của orchestrator chặn.
- **"newark bỏ qua PROXY_DIR env, dựa CWD==/app"** → factual đúng nhưng hôm nay vẫn hoạt động (CWD luôn `/app`); chỉ là fragility, không phải bug đang gây lỗi.
- **"proxy_type='none' tắt hết retry + overwrite lỗi thật"** → misread: `max_retries` không bị ép về 0 bởi proxy_type='none'.
- **"PROXY_HOST_DIR rỗng khi container auto-restart"** → đã phản ánh trong BUG-27 (xem mục 2), không tách bug mới.

> Các finding mục 4 của **06-19 vẫn giữ nguyên** giá trị "không-phải-bug" — không lặp lại ở đây.

---

## 6. Nhóm fix đề xuất (mới, theo quan hệ)

1. **False-success classification** (ưu tiên cao nhất): BUG-49 + BUG-53 — worker phải set `status='failed'` cho HTTP ≥ 400 / null response / http_code==0; dashboard mới phân loại đúng. Đây là lỗi âm thầm nhất.
2. **Dashboard integrity**: BUG-48 (strip `rq:queue:` prefix trước khi tạo `Queue`), BUG-57 (clamp page ≥ 1), BUG-56 (dedup SCAN bằng set — phần lớn đã dùng set, rà chỗ còn list).
3. **Routing đúng**: BUG-51 — route theo domain trích từ URL thật, không theo prefix ret_key client gửi (liên quan BUG-16 validate domain).
4. **Mount/path robustness sau move**: BUG-50 (check `isdir` trước khi mount chromium, theo pattern proxy), BUG-59 (anchor `workers/` theo path tuyệt đối hoặc env, không theo `__file__`).
5. **newark worker lifecycle**: BUG-52 (đóng browser/context trong `finally`), BUG-58 (guard page None/closed).
6. **Build hygiene**: BUG-54 (Dockerfile orchestrator dùng `requirements.txt` đã pin, đồng bộ version RQ với Dashboard).
7. **Slot edge**: BUG-55 (acquire slot bên trong `try` có `finally` release, dùng cờ boolean).

---

## 7. Checklist cho review lần sau

- [ ] BUG-13 → BUG-59 đã fix bao nhiêu? (cross-check `Bugs/` filename có `(FIXED)`)
- [ ] **BUG-14 đã rename file `(FIXED)` chưa?** (code đã fix 06-23 nhưng file chưa đánh dấu)
- [ ] False-success (BUG-49, 53) đã sửa? Worker mới có classify HTTP≥400/null/http_code==0 là failed?
- [ ] BUG-59 / path-after-move đã anchor `workers/` an toàn chưa? Có chạy được local lẫn trong container?
- [ ] `.env` có khôi phục default `PROXY_HOST_DIR` hay tài liệu hóa rằng phải qua start.sh? (BUG-27 dịch bối cảnh)
- [ ] Có domain worker mới nào ngoài fnac/newark? Có tuân thủ schema {domain, timestamp, status, http_code, html} + đóng browser trong finally?
- [ ] Các finding mục 5 (06-23) + mục 4 (06-19) vẫn đúng không-phải-bug? (nếu code đổi, kiểm lại)
- [ ] Chạy lại workflow audit: so confirmed count (12 lần này, 29 lần 06-19).

---

## 8. FLOW CHI TIẾT (reference — lần sau khỏi đọc lại code)

> Bản đồ flow đầy đủ kèm file:line cho commit `42858d5` (sau khi move vào `redis_server/`). Line đã verify lại trên code hiện tại, gồm cả fix BUG-14. Nếu code đổi, cập nhật phần này. ⚠️ = vị trí bug đang mở.

### 8.1 Trách nhiệm từng file
| File | Vai trò |
|---|---|
| [redis_server/config.py](../redis_server/config.py) | Đọc env (.env): REDIS_HOST/PORT, CRAWLER_NETWORK, PROXY_HOST_DIR (env-only, .env không còn default — xem §2), RESULT_TTL=3600, JOB_TIMEOUT_DEFAULT=120, CONTAINER_MEM_LIMIT=1g, CONTAINER_SHM_SIZE=2g, MAX_CONCURRENT_TOTAL=10. `get_max_concurrent(domain)` đọc `MAX_CONCURRENT_{DOMAIN}` (default 5); `get_job_timeout(domain)` đọc `JOB_TIMEOUT_{DOMAIN}` (default 120). |
| [Dashboard/app.py](../Dashboard/app.py) | Flask API (port 5000). Submit job `/api/submit-job`, hiển thị/monitor, clear/stop. `redis_conn` dùng `decode_responses=True`. |
| [redis_server/orchestrator.py](../redis_server/orchestrator.py) | Discover domains, spawn worker threads, ThreadSafeWorker, crash recovery. `redis_client` dùng `decode_responses=False` (bytes). |
| [redis_server/main.py](../redis_server/main.py) | `crawl_job` (RQ task), slot Lua acquire/release, job_state set/clear, spawn+wait container. `redis_client` dùng `decode_responses=True`. `docker_client` timeout=JOB_TIMEOUT_DEFAULT+120=240s (cứng — BUG-41). |
| [workers/{domain}/run.py](../workers/fnac/run.py) | Entrypoint container: đọc env URL/RET_KEY/PROXY_TYPE/REDIS_*, gọi sourceCode crawl, ghi `result:{ret_key}`. fnac và newark **giống hệt nhau** (chỉ khác prefix log). |
| [workers/{domain}/sourceCode/](../workers/fnac/sourceCode/) | Logic crawl thật (Playwright + proxy). fnac: `HtmlFetchResult.to_dict()` = schema result. newark: trả dict literal trực tiếp. |

### 8.2 Đường đi 1 job (happy path) — kèm line (đã cập nhật)
```
1. Client POST /api/submit-job {url, mode, proxy_type, ret_key}      app.py:748
   - domain = ret_key.split('_',2)[1]  (URL chỉ là fallback)         app.py:789-793  ⚠️BUG-51
   - set job_state:{ret_key}='queued' (ex=86400)                     app.py:817
   - queue.enqueue('main.crawl_job', url,domain,ret_key,proxy_type,  app.py:820-828
                   job_timeout=JOB_TIMEOUT_{DOMAIN}, job_id=ret_key)
   - return 202 {status:'queued'}                                    app.py:832-840

2. Orchestrator start_orchestrator()                                 orchestrator.py:227
   - _wait_for_redis() (retry 30×2s)                                 orchestrator.py:214 (gọi ở 229)
   - discover_worker_domains() = workers/*/ có Dockerfile            orchestrator.py:69-84  ⚠️BUG-59 (Path(__file__).parent)
   - cleanup_stale_workers(domains)                                  orchestrator.py:189
     → wipe rq:worker:* + slots:* → _retry_stale_jobs()
   - spawn get_max_concurrent(domain) threads/domain                 orchestrator.py:244-257
     mỗi thread = start_worker_for_domain → ThreadSafeWorker.work()

3. ThreadSafeWorker.dequeue_job_and_maintain_ttl                     orchestrator.py:60-66
   - while not _can_acquire_slots(domain): sleep(1); heartbeat()     orchestrator.py:24-39
     (soft pre-check: GET slots:global:total<TOTAL AND slots:domain:{d}<max)  ⚠️BUG-13 (heartbeat ngoài try)

4. crawl_job(url, domain, ret_key, proxy_type)                       main.py:70
   - _set_job_state 'queued'                                         main.py:74
   - _acquire_slot('global','total',TOTAL) — Lua INCR atomic         main.py:77 (Lua 17-27)
   - _acquire_slot('domain',domain,max)                              main.py:87
   - _set_job_state 'running'                                        main.py:94   ⚠️BUG-55 (khe rò slot)
   - result = _spawn_and_wait_container(...)                         main.py:98
   - _clear_job_state(ret_key)                                       main.py:99   ⚠️BUG-44 (không ở finally)
   - finally: release domain slot (112), global slot (115)

5. _spawn_and_wait_container                                         main.py:119
   - ensure image worker-{domain}:latest (load tar.gz nếu thiếu)     main.py:122-137
       thiếu cache → ghi result failed + clear state                 main.py:134-137  ✅BUG-14 đã fix
   - volumes: CHROMIUM_SNAP_DIR ro (KHÔNG check isdir)               main.py:139-140  ⚠️BUG-50
              PROXY_HOST_DIR→/app/Proxy ro nếu isdir                 main.py:146-147
   - containers.run(detach, remove, mem_limit, shm_size, SYS_ADMIN)  main.py:152-171
   - container.wait(timeout=get_job_timeout(domain))                 main.py:173  ⚠️BUG-21 (bỏ StatusCode)
   - đọc result:{ret_key} ← do container ghi                         main.py:189-193 (setdefault timestamp chỉ khi read-back — BUG-25)

6. Worker container run.py                                           run.py:11
   - process_single_request → crawl                                 run.py:26 → sourceCode/main.py:17
   - r.setex result:{ret_key} (TTL RESULT_TTL=3600)                  run.py:44   ⚠️BUG-22 (ngoài try)

7. Client poll GET /api/job/{ret_key} → đọc result:{ret_key}         app.py:480-491
```

### 8.3 Redis keys
| Key | TTL | Ai ghi | Ai xóa |
|---|---|---|---|
| `job_state:{ret_key}` | 86400 | app.py:817 (submit) / main.py:56 `_set_job_state` / orchestrator.py:170 (retry) | main.py:67 `_clear_job_state` (gọi ở 81/91/99/109/136), recovery |
| `result:{ret_key}` | 3600 (RESULT_TTL) | worker run.py:44 (success), main.py error paths (80/90/108/135/186/200) | dashboard clear, TTL |
| `slots:global:total` | 3600 (EXPIRE mỗi INCR) | Lua INCR (main.py:22) | DECR (main.py:49), cleanup wipe (orchestrator.py:201-209) |
| `slots:domain:{domain}` | 3600 | Lua INCR | DECR, cleanup wipe |
| `rq:queue:crawler:{domain}`, `rq:job:*`, `rq:worker:*`, `rq:failed:*` | RQ internal (**failed=1 năm!** BUG-26) | RQ | cleanup chỉ xóa `rq:worker:*` |

**Invariant**: `job_id == ret_key` ở mọi nơi. **Cảnh báo**: set `rq:queues` chứa **full key** `rq:queue:crawler:{d}` (không phải tên trần) — BUG-48.

### 8.4 Data contract — result dict
- **fnac**: `HtmlFetchResult.to_dict()` ([fnac extractor.py:31-41](../workers/fnac/sourceCode/extractor.py#L31)) = `{url, html, headers, http_code, cookies, elapsed_ms, error, status}`; `process_single_request` thêm `ret_key, total_elapsed_seconds, mode, proxy_type, log` ([fnac main.py:58-63](../workers/fnac/sourceCode/main.py#L58)).
- **newark**: trả dict literal trực tiếp trong [extractor.py](../workers/newark/sourceCode/extractor.py) — success ~line 310-313 lấy `http_code = response_data['status']`, nhưng nhiều nhánh dùng `http_code: 0` (~256/301/328/338) ⚠️BUG-53.
- **CẢ HAI thiếu `domain` và `timestamp`** top-level ở success path (BUG-24/25). main.py error paths thì CÓ; main.py read-back chỉ thêm `timestamp` (main.py:192), **không** thêm `domain`.
- **Phân loại sai success**: fnac ghi `status='success'` cho cả trang lỗi non-403/null (⚠️BUG-49); newark http_code=0 (⚠️BUG-53).
- Dashboard phân loại: `status=='success'` → finished, ngược lại → failed ([app.py:169](../Dashboard/app.py#L169), [app.py:269](../Dashboard/app.py#L269)).

### 8.5 Concurrency model — KHÔNG đổi so với 06-19
Xem **§1.5 của [2026-06-19_flow-audit.md](2026-06-19_flow-audit.md)** (vẫn nguyên hiệu lực). Tóm tắt: mỗi domain `MAX_CONCURRENT_{DOMAIN}` thread × `ThreadSafeWorker(SimpleWorker)` (orchestrator.py:42), `TimerDeathPenalty` (orchestrator.py:50), job chạy **in-process không fork**. 2 lớp slot: global (Lua atomic, max TOTAL) + domain (max per-domain). `_can_acquire_slots` = soft pre-check; Lua INCR trong crawl_job = hard gate. Single-domain an toàn; multi-domain overcommit (Σ domain max > TOTAL) mới có TOCTOU (BUG-17).

### 8.6 Crash recovery — KHÔNG đổi so với 06-19
`_retry_stale_jobs` ([orchestrator.py:105-186](../redis_server/orchestrator.py#L105)): scan `job_state:*`, với state queued/running:
- có `result:{ret_key}` → xóa state, skip (orchestrator.py:142-145)
- RQ status 'queued' → skip (giữ); **'finished'/'failed' → xóa state, skip** ⚠️BUG-20 ('failed' không result bị vứt sai, orchestrator.py:154-157)
- NoSuchJobError → re-enqueue, `job_id=ret_key` (orchestrator.py:163-169)
Persistence: Redis AOF (`--appendonly yes`) + docker volume.
