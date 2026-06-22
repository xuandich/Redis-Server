# Code Review — Flow Audit (2026-06-19)

**Commit**: `cfe7ef6` (branch `thread-simple-worker`)
**Phương pháp**: Multi-lens workflow audit — 8 dimensions fan-out → adversarial verification → completeness critic. 65 agents, 48 raw findings → **29 confirmed**, 19 refuted.
**Phạm vi**: main.py, orchestrator.py, config.py, Dashboard/app.py, workers/fnac/{run.py, sourceCode/}, docker-compose.yml, start.sh, stop.sh.

> Mục đích file này: snapshot trạng thái để lần review sau **so sánh** — bug nào đã fix, bug nào còn, finding nào đã bị bác bỏ (đừng flag lại).

---

## 1. FLOW CHI TIẾT (reference — lần sau khỏi đọc lại code)

> Đây là bản đồ flow đầy đủ kèm file:line. Nếu code đổi, cập nhật phần này.

### 1.1. Trách nhiệm từng file
| File | Vai trò |
|---|---|
| `config.py` | Đọc env (.env): REDIS_HOST/PORT, CRAWLER_NETWORK, PROXY_HOST_DIR, RESULT_TTL=3600, JOB_TIMEOUT=120, CONTAINER_MEM_LIMIT=1g, CONTAINER_SHM_SIZE=2g, MAX_CONCURRENT_TOTAL=10, MAX_CONCURRENT_{DOMAIN}. `get_max_concurrent(domain)` đọc `MAX_CONCURRENT_{DOMAIN}` (default 5). |
| `Dashboard/app.py` | Flask API (port 5000). Nhận job qua `/api/submit-job`, hiển thị/monitor, clear. `redis_conn` dùng `decode_responses=True`. |
| `orchestrator.py` | Discover domains, spawn worker threads, ThreadSafeWorker, crash recovery. `redis_client` dùng `decode_responses=False`. |
| `main.py` | `crawl_job` (RQ task), slot Lua acquire/release, job_state set/clear, spawn+wait container. `redis_client` dùng `decode_responses=True`. `docker_client` timeout=JOB_TIMEOUT+120=240s. |
| `workers/{domain}/run.py` | Entrypoint container: đọc env URL/RET_KEY/PROXY_TYPE, gọi sourceCode crawl, ghi `result:{ret_key}`. |
| `workers/{domain}/sourceCode/` | Logic crawl thật (Playwright + proxy). `extractor.py:HtmlFetchResult.to_dict()` = schema result. |

### 1.2. Đường đi 1 job (happy path) — kèm line
```
1. Client POST /api/submit-job {url, mode, proxy_type, ret_key}     app.py:746
   - _extract_domain_from_url(url) → domain                          app.py:729-743 / 786
   - set job_state:{ret_key}='queued' (TTL 86400)                    app.py:810
   - queue.enqueue('main.crawl_job', url,domain,ret_key,proxy_type,  app.py:813-821
                   job_timeout=600, job_id=ret_key)
   - return 202 {status:'queued'}                                    app.py:825-833

2. Orchestrator start_orchestrator()                                 orchestrator.py:227
   - _wait_for_redis() (retry 30×2s)                                 orchestrator.py:214 (gọi ở 229)*
   - discover_worker_domains() = workers/*/ có Dockerfile            orchestrator.py:69-84
   - cleanup_stale_workers(domains)                                  orchestrator.py:189
     → xóa rq:worker:* + slots:* → _retry_stale_jobs()
   - spawn get_max_concurrent(domain) threads/domain                 orchestrator.py:231-242
     mỗi thread = start_worker_for_domain → ThreadSafeWorker.work()

3. ThreadSafeWorker.dequeue_job_and_maintain_ttl                     orchestrator.py:60-66
   - while not _can_acquire_slots(domain): sleep(1); heartbeat()
     _can_acquire_slots = GET slots:global:total < TOTAL            orchestrator.py:24-39
                          AND GET slots:domain:{d} < max (soft check)
   - super().dequeue → pick job

4. crawl_job(url, domain, ret_key, proxy_type)                       main.py:70
   - _set_job_state 'queued'                                         main.py:74
   - _acquire_slot('global','total',TOTAL) — Lua INCR atomic         main.py:77 (Lua 17-27)
   - _acquire_slot('domain',domain,max)                              main.py:87
   - _set_job_state 'running'                                        main.py:94
   - result = _spawn_and_wait_container(...)                         main.py:98
   - _clear_job_state(ret_key)                                       main.py:99
   - finally: release domain slot (103), global slot (106)

5. _spawn_and_wait_container                                         main.py:110
   - đảm bảo image worker-{domain}:latest (load tar.gz nếu thiếu)    main.py:112-125
   - containers.run(detach=True, remove=True, network=crawler-net,   main.py:134-153
       volumes={CHROMIUM_SNAP_DIR ro, PROXY_HOST_DIR→/app/Proxy ro},
       env={URL,RET_KEY,PROXY_TYPE,REDIS_HOST,...}, mem_limit, shm_size, cap_add SYS_ADMIN)
   - container.wait(timeout=JOB_TIMEOUT=120)                         main.py:155
   - đọc result:{ret_key} ← do container ghi                         main.py:171

6. Worker container run.py                                           run.py:11
   - process_single_request → crawl                                 run.py:26 / sourceCode/main.py:17
   - r.setex result:{ret_key} (TTL RESULT_TTL=3600)                  run.py:44

7. Client poll GET /api/job/{ret_key} → đọc result:{ret_key}         app.py:478-493
```
\* `_wait_for_redis` thêm ở commit Redis healthcheck (orchestrator.py:214, gọi đầu start_orchestrator line 229).

### 1.3. Redis keys
| Key | TTL | Ai ghi | Ai xóa |
|---|---|---|---|
| `job_state:{ret_key}` | 86400 | app.py submit / main.py _set_job_state / retry | main.py _clear_job_state (line 99/81/91), recovery |
| `result:{ret_key}` | 3600 | worker run.py (success), main.py (error paths 80/90/168/182) | dashboard clear, TTL |
| `slots:global:total` | 3600 (reset mỗi acquire) | Lua INCR (main.py:22) | DECR (main.py:49), cleanup wipe |
| `slots:domain:{domain}` | 3600 | Lua INCR | DECR, cleanup wipe |
| `rq:queue:crawler:{domain}`, `rq:job:*`, `rq:worker:*`, `rq:failed:*` | RQ internal (failed=1 năm!) | RQ | cleanup chỉ xóa rq:worker:* |

**Invariant**: `job_id == ret_key` ở mọi nơi.

### 1.4. Data contract — result dict
Schema do worker ghi (`HtmlFetchResult.to_dict()`, extractor.py:31-41):
`{url, html, headers, http_code, cookies, elapsed_ms, error, status}`
+ process_single_request thêm: `ret_key, total_elapsed_seconds, mode, proxy_type` (sourceCode/main.py:59-65).
**THIẾU `domain` và `timestamp`** ở success path (xem BUG-24/25). Error paths của main.py thì CÓ domain+timestamp.
Dashboard phân loại: `status=='success'` → finished, ngược lại → failed (app.py:169-170/267-270).

### 1.5. Concurrency model
- Mỗi domain: `MAX_CONCURRENT_{DOMAIN}` threads, mỗi thread 1 ThreadSafeWorker, xử lý 1 job tại 1 thời điểm.
- Slot global (Lua atomic, max TOTAL) + slot domain (max per-domain) = 2 lớp giới hạn.
- `_can_acquire_slots` (orchestrator) = soft pre-check; Lua INCR trong crawl_job = hard gate.
- Single-domain an toàn (threads = domain max); multi-domain overcommit (Σ domain max > TOTAL) mới có TOCTOU (BUG-17).
- Jobs chạy IN-PROCESS (SimpleWorker, không fork) → không thể kill 1 thread mà process sống.

### 1.6. Crash recovery
`_retry_stale_jobs` (orchestrator.py:105-186): scan `job_state:*`, với state queued/running:
- có result:{ret_key} → xóa state, skip
- RQ status 'queued' → skip (giữ); 'finished'/'failed' → xóa state, skip **(BUG-20: 'failed' không result bị vứt sai)**
- NoSuchJobError → re-enqueue (job_id=ret_key)
Persistence: Redis AOF (`--appendonly yes`) + docker volume.

---

## 2. Trạng thái bug tại thời điểm review

### Đã FIX trước review (BUG-01 → BUG-12)
Zombie reaper, dead-horse, slot leak, fork-in-thread (→ SimpleWorker + TimerDeathPenalty), result double-write, slot timeout 300→60, fail-closed slot check, sort-by-timestamp, clear-state dedup, imports-at-top, finished/failed timestamp, rq:queues replace.

### Tồn đọng trước review (BUG-13 → BUG-19) — phát hiện thủ công
| ID | Sev | Tóm tắt | File |
|---|---|---|---|
| BUG-13 | MED-HIGH | heartbeat() trong slot-loop không bọc try → Redis blip giết thread vĩnh viễn | orchestrator.py:60-66 |
| BUG-14 | MED | image-not-found path không ghi result → client 404 | main.py:124-125 |
| BUG-15 | MED | containers.run() không bọc try → job kẹt 'running' | main.py:134 |
| BUG-16 | MED | submit-job nhận domain không có worker → stuck queued | app.py:741 |
| BUG-17 | LOW | TOCTOU slot pre-check (chỉ multi-domain overcommit) | orchestrator.py:24 |
| BUG-18 | LOW | get_jobs_by_state không sort → pagination unstable | app.py:189 |
| BUG-19 | LOW | wait()+remove=True race → đè good result | main.py:155 |

### MỚI từ workflow audit (BUG-20 → BUG-38)
| ID | Sev | Tóm tắt | File |
|---|---|---|---|
| **BUG-20** | **HIGH** | recovery vứt job RQ-'failed' không result → mất vĩnh viễn (mảnh ghép của BUG-15) | orchestrator.py:154-157 |
| BUG-21 | MED | container.wait() bỏ qua StatusCode → exit≠0 coi như success | main.py:155-156 |
| BUG-22 | MED | run.py ghi result NGOÀI try → Redis blip lúc setex mất result | run.py:44 |
| BUG-23 | MED | orphan worker containers + double-spawn khi orchestrator crash | main.py:134 / stop.sh:41 / orchestrator.py:189 |
| BUG-24 | MED | result success thiếu 'domain' → dashboard by_domain='unknown' | extractor.py:31 + main.py:171 |
| BUG-25 | MED | result success thiếu 'timestamp' → sort sai (vô hiệu BUG-08 cho success) | extractor.py:31 + main.py:171 |
| BUG-26 | MED | failed RQ jobs giữ 1 năm (không set failure_ttl) → Redis phình | orchestrator.py:92-99 |
| BUG-27 | MED | PROXY_HOST_DIR relative → mount hỏng khi `docker compose up` trực tiếp | .env:7 |
| BUG-28 | LOW | int(page) ngoài try → ?page=abc ⇒ 500 | app.py:78 |
| BUG-29 | LOW | queued URL luôn 'N/A' (bytes key vs decode_responses=True) | app.py:141 |
| BUG-30 | LOW | clear_state log đếm cộng dồn qua queue | app.py:615 |
| BUG-31 | LOW | _acquire_slot nuốt lỗi Redis → mislabel 'slot timeout' | main.py:39-41 |
| BUG-32 | LOW | _release_slot set(key,0) xóa TTL (cosmetic) | main.py:50-51 |
| BUG-33 | LOW | shm_size 2g > mem_limit 1g → Chromium OOM | main.py:150-151 |
| BUG-34 | LOW | image auto-load không lock → N threads load 300MB | main.py:112-125 |
| BUG-35 | LOW | field 'mode' nhận+echo nhưng không truyền xuống worker | app.py:775-821 |
| BUG-36 | LOW | stop.sh -clear báo success cả khi thiếu redis-cli | stop.sh:26-36 |
| BUG-37 | LOW | start.sh -quiet sleep 3s rồi báo success không check health | start.sh:161-168 |
| BUG-38 | LOW | RESULT_TTL(1h) < job_state(24h) → restart >1h re-crawl URL đã xong | orchestrator.py:142 |

**Tổng đang mở: 26 bug (BUG-13 → BUG-38).** Chi tiết từng bug trong `Bugs/`.

---

## 3. Nhóm fix đề xuất (theo quan hệ, không theo ID)

1. **Result-write consistency** (path luôn ghi result + clear state): BUG-14, BUG-15, BUG-20, BUG-21, BUG-22. → Mọi nhánh kết thúc của crawl_job/spawn phải (a) ghi result:{ret_key}, (b) clear job_state; recovery re-enqueue 'failed'-without-result.
2. **Result schema backfill** (1 fix): BUG-24 + BUG-25 — crawl_job read-back inject domain+timestamp rồi **re-write** result key.
3. **Worker thread robustness**: BUG-13 (bọc heartbeat + resurrection wrapper), BUG-31.
4. **Container lifecycle**: BUG-23 (label + cleanup orphan), BUG-33, BUG-34.
5. **Dashboard hygiene**: BUG-18, BUG-28, BUG-29, BUG-30, BUG-35.
6. **Ops/deploy**: BUG-26, BUG-27, BUG-36, BUG-37.
7. **TTL/recovery edge**: BUG-38, BUG-16, BUG-17.

---

## 4. Đã ADVERSARIALLY BÁC BỎ — đừng flag lại lần sau

Đã đọc code thật và xác nhận **KHÔNG phải bug**:
- **_release_slot DECR+SET race → over-admit**: SAI. Lua acquire atomic; clamp set(0) chỉ khi val<0, không bao giờ đẩy quá MAX.
- **TimerDeathPenalty không interrupt được container.wait()**: đúng về Python internals nhưng đã có socket timeout `docker.from_env(timeout=JOB_TIMEOUT+120)`=240s chặn → không treo quá 240s.
- **TTL mismatch result(1h)<job_state(24h) làm job_state resurface 'running'**: SAI — line 99 `_clear_job_state` LUÔN chạy khi có result write. (Khác BUG-38: BUG-38 là re-crawl khi state kẹt do crash, không phải resurface bình thường.)
- **models.py ProductResult schema lệch**: dead code, không ai import → không phải bug.
- **q.empty() orphan rq:job:* hashes**: SAI cho RQ 2.9.1 — empty() Lua có `del` job hash.
- **single-domain TOCTOU slot**: không thể (5 fnac threads = domain max 5; BUG-17 chỉ multi-domain overcommit/misconfig).
- **register_script() mỗi call**: chỉ tính SHA1 local, không network I/O → micro-nit, không bug.
- **_retry_stale_jobs double-enqueue overlapping runs**: SAI — chạy 1 lần/startup, single-thread, trước khi spawn worker.
- **crash giữa acquire-slot và set-running leak slot (1 thread)**: SAI — job chạy in-process, không thể kill 1 thread mà process sống; cleanup chạy trước mọi acquire khi restart.
- **run.py env vars ngoài try (KeyError)**: main.py luôn set env + có fallback "No result from container" → không 404 vĩnh viễn.
- **slots:* sliding EXPIRE leak**: cleanup chạy trước spawn mọi restart → window đóng.
- **.env xargs export hỏng giá trị có space**: .env hiện tại toàn token không space; PROXY_HOST_DIR bị override (xem BUG-27).
- **docker-compose ${REDIS_HOST} empty**: .env committed có giá trị → OK as-shipped.

---

## 5. Checklist cho review lần sau

- [ ] BUG-13 → BUG-38 đã fix chưa? (cross-check `Bugs/` filenames có `(FIXED)`)
- [ ] Có bug mới phát sinh từ các fix không?
- [ ] Các finding ở mục 4 vẫn đúng là không-phải-bug? (nếu code đổi, kiểm lại)
- [ ] Worker domain mới (ngoài fnac) có tuân thủ result schema {domain, timestamp, status, http_code, html}?
- [ ] Chạy lại workflow audit: so confirmed count với lần này (29).
