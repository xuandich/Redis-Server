# Code Review — Flow Audit (2026-06-26)

**Commit**: `451c40f` (branch `main`) + thay đổi CHƯA COMMIT trên `redis_server/orchestrator.py` (fix BUG-13 phiên này).
**Phương pháp**: Workflow re-audit đối kháng — 5 pha: (1) verify 4 fix gần đây có đúng + có regression không, (2) đối chiếu flow map §8 với code hiện tại, (3) reconcile 59 bug, (4) 8-dimension fan-out tìm bug MỚI, (5) adversarial verify từng finding. **67 agents, 30 structured-result hoàn thành; 37 agent verify ở pha 5 bị hủy giữa chừng do session limit** → reviewer chính (Opus) tự verify thủ công các finding HIGH chưa được agent bác bỏ/xác nhận, dựa trên source RQ 2.9.1 đã cài + code live.
**Phạm vi**: như 06-23 + soi sâu lifecycle `retry_count` (logic mới của BUG-20), tương tác của fix BUG-13 với nội bộ RQ `work()`.

> File này nối tiếp [2026-06-23_flow-audit.md](2026-06-23_flow-audit.md) và [2026-06-19_flow-audit.md](2026-06-19_flow-audit.md). Ghi **delta** trạng thái + **finding mới** + đối chiếu checklist lần trước. Điểm khác biệt lớn nhất so với 06-23: đã có **4 fix** (BUG-13/20/24/49) đi vào code; review này tập trung kiểm chứng chúng và tác động phụ.

---

## 1. Đối chiếu checklist 2026-06-23 (mục 7 của file cũ)

| Checklist cũ | Kết quả đối chiếu hôm nay |
|---|---|
| **BUG-13 → BUG-59 đã fix bao nhiêu?** | Thêm **BUG-20, BUG-24, BUG-49** đã fix + đánh dấu `(FIXED)`; **BUG-13** fix trong code (chưa commit, file chưa rename); **BUG-27** thực ra đã fix từ commit a34c2d4 nhưng file chưa rename. Còn lại OPEN. |
| **BUG-14 đã rename file `(FIXED)` chưa?** | ✅ Đã rename: `BUG-14(FIXED)_MEDIUM_image-not-found-no-result-write.md`. |
| **False-success (BUG-49, 53) đã sửa?** | **BUG-49 (fnac) ĐÃ sửa** đúng — 403/429/503 retry-rồi-fail, `http_code==0 hoặc >=400` → failed ([extractor.py:280-291](../workers/fnac/sourceCode/extractor.py#L280)). **BUG-53 (newark) VẪN OPEN** — `main.py:43` classify `success` chỉ dựa `html` truthiness, bỏ qua `http_code` (thường = 0). |
| **BUG-59 / path-after-move đã anchor `workers/` an toàn?** | **CHƯA.** `orchestrator.py:81` vẫn `Path(__file__).parent / 'workers'` → trỏ `redis_server/workers` (không tồn tại) khi chạy local. Chỉ chạy được trong container nhờ COPY + bind-mount trùng nhau. |
| **`.env` có khôi phục default `PROXY_HOST_DIR`?** | **.env CÓ** (absolute path) ⟹ **BUG-27 đã hết tái hiện** (xem §2). NHƯNG **`.env.example` vẫn KHÔNG có dòng `PROXY_HOST_DIR`** ⟹ `cp .env.example .env` cho người mới → proxy bị tắt âm thầm (finding mới, §4). |
| **Có domain worker mới ngoài fnac/newark?** | Không. Vẫn `workers/{fnac,newark}` (+ `Proxy`). `MAX_CONCURRENT_AMAZON`/`QUEUE_AMAZON` vẫn là config chết (BUG-45/46). |
| **Finding §5 (06-23) + §4 (06-19) vẫn đúng không-phải-bug?** | Còn đúng. Bổ sung 3 finding mới bị **bác bỏ** lần này (§5). |
| **So confirmed count** | 06-19: 29/48 · 06-23: 12/20 · **06-26: pha verify bị cắt do session limit** — 7/7 verdict hoàn thành đều khớp finder, phần còn lại reviewer tự verify (§4). |

---

## 2. Delta trạng thái bug từ 2026-06-23

**Tại 06-23**: 59 bug, 16 FIXED / 43 OPEN. **Hôm nay**: 59 bug + 5–6 finding mới (đề xuất BUG-60→64). Trạng thái: **20 file `(FIXED)` + BUG-13 & BUG-27 fixed-trong-code-chưa-rename = 22 đã giải quyết / 37 OPEN.**

### Đã FIX kể từ 06-23
- **BUG-20** (recovery vứt job RQ-`failed` không result) — fixed: nhánh `failed` re-enqueue thay vì skip, cap `retry_count>=3` ghi result failed vĩnh viễn, `retry_count` lưu trong `job_state` ([orchestrator.py:197-234](../redis_server/orchestrator.py#L197)) + được `_set_job_state` bảo toàn ([main.py:54-71](../redis_server/main.py#L54)). Verify: đúng end-to-end.
- **BUG-24** (success result thiếu `domain`) — fixed: read-back `setdefault('timestamp'/'domain'/'url')` rồi re-write ([main.py:197-204](../redis_server/main.py#L197)). Không regression (setdefault không đè giá trị worker).
- **BUG-49** (fnac non-403 mark success) — fixed cho fnac (xem §1).
- **BUG-13** (worker thread chết khi Redis blip) — **fix trong code phiên này (chưa commit), nhưng bản fix ĐẦU đã không trọn vẹn — xem §3.** File chưa rename `(FIXED)`.
- **BUG-27** (PROXY_HOST_DIR relative) — **thực ra đã fixed từ commit a34c2d4** (`.env` đổi sang absolute, `start.sh` bỏ override). File chưa rename `(FIXED)`.

### Đổi trạng thái (không full-fix)
- **BUG-23** (orphan worker containers) — **PARTIALLY-FIXED**: `stop.sh:42-50` lọc theo network để dừng/xóa MỌI container (kể cả worker) ⟹ path `stop.sh` đã sạch. NHƯNG kịch bản gốc vẫn còn: `containers.run` thiếu `name=`/`labels=` ([main.py:160-179](../redis_server/main.py#L160)) → orphan không truy vết được; `cleanup_stale_workers` chỉ xóa Redis key, **không** `containers.list()/kill()`; orchestrator-crash → re-enqueue (`job_id=ret_key`) trong khi orphan cũ còn chạy → **double-spawn + late write đè result mới**.
- **BUG-41** (docker client timeout cứng 240s) — **nhẹ hơn rated**: `container.wait(timeout=720)` truyền `timeout` xuống `_post` → **override** socket-timeout per-request (docker-py `_set_request_timeout` chỉ dùng default khi thiếu `timeout`), nên newark **KHÔNG** bị cắt ở 240s. Chỉ `images.get/containers.run/container.kill` còn bị giới hạn 240s khi daemon treo. → Hạ severity.

### Vẫn OPEN, đã xác nhận lại trên code hiện tại
BUG-16,17,18,19,21,22,25,26,28,29,30,31,32,33,34,35,36,37,38,39,40,44,45,46,48,50,51,52,53,54,55,56,57,58,59 — tất cả còn nguyên cơ chế đúng như mô tả (chỉ lệch line number, xem §8). Các fix FIXED cũ (BUG-14/15/42/43/47) đã verify **không regression**.

---

## 3. ⚠️ Tác động fix phiên này — BUG-13 chỉ fix MỘT NỬA (đã sửa lại)

> Đây là phát hiện quan trọng nhất lần review này. Bản fix BUG-13 ĐẦU TIÊN (commit-pending lúc giữa phiên) **không đạt mục tiêu**; reviewer tự verify trong source RQ 2.9.1 và sửa lại.

**Cơ chế:** `rq.worker.Worker.work()` (RQ 2.9.1) bọc vòng lặp chính trong `try/except`:
```
except redis.exceptions.TimeoutError:  -> log + break   (return bình thường)
except StopRequested:                  -> break
except SystemExit:                     -> raise          (chỉ cái này raise)
except:  # noqa                        -> log + break   (return bình thường)
finally: self.teardown(); return bool(completed_jobs)
```
Tức là **Redis blip lúc `execute_job()`/`heartbeat()` → `work()` RETURN bình thường, KHÔNG raise.**

- Bản fix đầu: `dequeue_job_and_maintain_ttl` có backoff (✅ cứu nhánh **chờ slot**), và `start_worker_for_domain` bọc `worker.work()` trong `while True` nhưng **`break` khi work() return bình thường**. ⟹ Blip lúc **thực thi job** → work() return → `break` → **thread vẫn chết vĩnh viễn = đúng triệu chứng BUG-13.**
- Phụ: restart cùng tên worker → `register_birth()` raise `ValueError` nếu key `rq:worker:{name}` còn sống chưa có field `death` (xảy ra khi Redis còn down lúc teardown → `register_death` cũng fail). ValueError bị `except Exception` nuốt → kẹt restart mỗi 5s tới khi key hết TTL ~480s.

**Đã sửa** ([orchestrator.py:97-140](../redis_server/orchestrator.py#L97)):
1. Vì cấu hình này (`burst=False`, no signal handler, no `max_jobs`/`max_idle_time`) → **work() return luôn đồng nghĩa lỗi cần restart** → bỏ `break`, restart trên mọi lần return (sleep 5s).
2. Chỉ `break` khi `KeyboardInterrupt`/`SystemExit` (shutdown).
3. `redis_client.delete(worker_key)` best-effort trước mỗi (re)start để tránh `register_birth` ValueError.

> Các fix BUG-20/24/49 **không gây regression** (verify riêng). Lưu ý phụ: result give-up của BUG-20 ghi TTL **86400s** ([orchestrator.py:218](../redis_server/orchestrator.py#L218)) trong khi result thường dùng `RESULT_TTL`=3600s ⟹ §8.3 "result TTL=3600" không còn đúng đồng nhất.

---

## 4. Finding MỚI lần này (đề xuất BUG-60 → BUG-64) + raw chưa verify

### Đã CONFIRM (reviewer tự verify hoặc verdict agent hoàn thành) — nên tạo file bug
| ID đề xuất | Sev | Tóm tắt | File | Verify bởi |
|---|---|---|---|---|
| **BUG-60** | **HIGH** | **Dashboard submit ghi `job_state` KHÔNG có `retry_count`** (`redis_conn.set`, ghi đè vô điều kiện) → re-submit cùng `ret_key` reset cap BUG-20 về 0 → job luôn-lỗi re-enqueue vô hạn. `main.py:_set_job_state` cố tình bảo toàn `retry_count` nhưng dashboard không. | [Dashboard/app.py:809-817](../Dashboard/app.py#L809) | Reviewer (đọc code) |
| **BUG-61** | MED-HIGH | `register_birth` name-collision: restart worker cùng tên khi `rq:worker:{name}` còn sống chưa `death` → ValueError → kẹt restart tới ~480s. (Phát lộ bởi restart-loop của BUG-13.) **Đã phòng** bằng delete-key trước restart. | [orchestrator.py:97-140](../redis_server/orchestrator.py#L97) + rq base.py:900 | Reviewer (source RQ) |
| **BUG-62** | MED | `start.sh:88-89` hardcode tên image `redis_server-orchestrator/dashboard` = basename thư mục (compose không set `name:`). Clone/đổi tên thư mục + `docker compose up --no-build` → image không khớp → stack không lên. | [start.sh:88-89](../start.sh#L88), [docker-compose.yml](../docker-compose.yml) | Reviewer (đọc code) |
| **BUG-63** | LOW | Newark bỏ qua env `PROXY_DIR` (orchestrator có truyền) và hardcode path tương đối `Proxy/buyproxies_List.xlsx` ([main.py:24](../workers/newark/sourceCode/main.py#L24)); fnac thì honor `PROXY_DIR`. Đổi CWD/WORKDIR/mount → newark crawl 0 proxy âm thầm (`load_proxies_from_excel` trả `[]` không raise). Latent (hiện CWD=/app nên đúng). | workers/newark/sourceCode/main.py:24 | Verdict agent (is_new=true) |
| **BUG-64** | LOW | fnac BUG-49 chỉ gate `>=400`, **bỏ band 3xx (300-399)** → 3xx (vd 304) lọt `mark_success`. Hẹp hơn spec của chính bug doc ("chỉ success khi 200≤code<300"). Trigger hiếm (browser auto-follow redirect; incognito mới nên ít 304). | [extractor.py:287](../workers/fnac/sourceCode/extractor.py#L287) | Verdict agent (is_new=true) |

### RAW → ĐÃ VERIFY qua harness pha 5 (2026-06-26, run `wf_2feafe0d` / `wh1a7uml7`, 12 agent skeptic)
12 finding RAW đã chạy qua `phase5-audit-verify`: **4 confirmed-new → tạo file bug, 8 bác bỏ → §5.** Kết quả thô: `Reviews_Project/audit/results/verdicts.json`.

| Finding | Verdict | → |
|---|---|---|
| 200-with-block fnac (content-based, khác BUG-49/64 về dải status) | real+new MED | **BUG-65** |
| .env.example thiếu PROXY_HOST_DIR | real+new MED | **BUG-66** |
| dashboard seen_result che job re-running thành "failed" | real+new LOW (hạ từ MED) | **BUG-67** |
| dashboard list view bỏ `retry_count` | real+new LOW | **BUG-68** |

> Cơ chế "200-with-block cho newark" gộp vào BUG-53 (newark đã có sẵn vấn đề http_code/html); BUG-65 chỉ cho fnac.

---

## 5. Đã ADVERSARIALLY BÁC BỎ lần này — đừng flag lại

- **"docker client timeout 240s giết newark (720s) ở `container.wait`"** → **SAI**: `wait(timeout=720)` override socket-timeout per-request (docker-py `_set_request_timeout`). wait() an toàn; chỉ admin-call khác (`images.get/run/kill`) bị 240s = BUG-41 (nhẹ).
- **"Dashboard đếm newark false-success làm phồng success_rate là bug của dashboard"** → **bác bỏ**: dashboard chỉ passthrough trung thực field `status` của worker. Đây là triệu chứng hạ nguồn của **BUG-53**, fix BUG-53 là hết — không phải bug dashboard độc lập.
- **"`cache_file` CWD-relative ở main.py:134 gây fail load image"** → **bác bỏ**: orchestrator luôn chạy trong container `WORKDIR=/app`; kịch bản local-run thì `discover_worker_domains` đã return `[]` trước đó (= **BUG-59**), không tới được dòng cache_file.

### Thêm — bác bỏ qua pha 5 (2026-06-26). Mấu chốt: **`_retry_stale_jobs` chạy single-thread lúc startup TRƯỚC khi spawn worker** (orchestrator.py:299 gọi cleanup→recovery, rồi mới `Thread().start()` ở 306-314) → mọi race "recovery vs worker" đều bất khả thi.
- **"retry_count non-atomic GET+SETEX → lost-update"** → bác bỏ: recovery và worker KHÔNG chạy đồng thời (recovery xong mới spawn worker). Không có interleaving.
- **"Re-enqueue window: job dequeue-able trước khi job_state retry_count ghi"** → bác bỏ: không worker nào chạy lúc recovery → không ai dequeue trong cửa sổ đó.
- **"Slot-wait bỏ đói RQ maintenance → stale rq:worker tích lũy"** → bác bỏ: `clean_worker_registry` KHÔNG xóa hash `rq:worker:{name}` (chỉ xóa set membership); và cleanup_stale_workers ở startup + delete-key-trước-restart (BUG-61) đã dọn. Không tích lũy unbounded.
- **"Không graceful stop khi slot-wait (_stop_requested)"** → bác bỏ: `signal.signal()` raise `ValueError` ngoài main thread → no-op `_install_signal_handlers` là **BẮT BUỘC** cho worker chạy trong daemon thread; "fix" đề xuất là bất khả thi.
- **"Backoff bỏ heartbeat lúc Redis outage"** → bác bỏ: heartbeat() được GỌI mỗi vòng (line 68) và FAIL vì Redis down (không phải "bỏ"); không thể refresh key trên Redis chết; tự lành khi Redis về.
- **"Write-flap >480s làm hết hạn worker key"** → bác bỏ: cơ chế đúng nhưng hậu quả không vật chất (worker tự re-dequeue khi write về; key chỉ là record monitoring).
- **"1s heartbeat polling load (regression từ BUG-13)"** → bác bỏ: vòng `sleep(1)+heartbeat` ĐÃ có từ trước BUG-13 (commit 8fe1c7b), không phải regression; chưa từng có bản "BLPOP đơn lúc saturation".
- **"`cache_file` CWD-relative" (lặp lại)** → bác bỏ lần 2: prod luôn `WORKDIR=/app`.

> Các finding §5 (06-23) + §4 (06-19) vẫn giữ giá trị không-phải-bug.

---

## 6. Nhóm fix đề xuất (theo ưu tiên, sau review này)

1. **Hoàn tất robustness worker thread** (HIGH): ✅ BUG-13 (đã sửa restart-on-return + delete stale key), **BUG-60** (dashboard submit phải bảo toàn `retry_count` như `main.py:_set_job_state`), BUG-61 (đã phòng). → Đảm bảo cap BUG-20 không bị vô hiệu.
2. **False-success còn lại** (HIGH/MED): BUG-53 (newark gate `200≤code<300` + verify selector sản phẩm thay vì chỉ '/dp/'), 200-with-block (content-check), BUG-64 (fnac thêm band 3xx).
3. **Container lifecycle / double-spawn** (MED): BUG-23 phần orchestrator-crash (label container + `containers.kill()` orphan trong cleanup trước re-enqueue), BUG-19/21 (đọc StatusCode + guard result tồn tại trước khi ghi error).
4. **Dashboard integrity** (MED-HIGH): BUG-48 (strip `rq:queue:` prefix), BUG-18/57 (sort + clamp page≥1), BUG-28 (int parse trong try), BUG-51/16 (route + validate domain theo worker thật).
5. **Deploy hygiene** (MED): BUG-62 (set `name:` trong compose hoặc COMPOSE_PROJECT_NAME), BUG-40 (rebuild theo mtime/hash), BUG-54 (Dockerfile pin + dùng requirements.txt), .env.example thêm PROXY_HOST_DIR.
6. **Path robustness** (LOW): BUG-59 (anchor `workers/` theo env/absolute), BUG-63 (newark đọc `PROXY_DIR`).
7. **Slot/recovery edge** (LOW-MED): BUG-55, retry_count non-atomic/re-enqueue-window (dùng Lua/atomic hoặc ghi job_state trước enqueue), BUG-26/38 (failure_ttl + TTL skew).

---

## 7. Checklist cho review lần sau

- [ ] BUG-13 đã commit + rename `(FIXED)` chưa? Đã rebuild+save image orchestrator chưa (vì code đổi)?
- [ ] BUG-27 rename `(FIXED)` chưa?
- [ ] **BUG-60** (dashboard clobber retry_count) đã fix chưa? Cap BUG-20 còn bị vô hiệu khi re-submit không?
- [ ] Tạo file bug cho BUG-60→64 chưa? Các finding RAW §4 đã được verify/giáng cấp chưa?
- [ ] False-success: BUG-53 + 200-with-block + BUG-64 đã xử lý? Worker mới có gate `200≤code<300` + content-check?
- [ ] BUG-23: container đã có `name/labels` + cleanup có `kill` orphan trước re-enqueue chưa?
- [ ] Các finding §5 (06-26) vẫn đúng không-phải-bug? (đặc biệt docker-timeout — nếu đổi sang custom HTTP client thì kiểm lại)
- [ ] Chạy lại workflow audit với session-budget đủ để pha adversarial-verify chạy trọn (lần này bị cắt).

---

## 8. FLOW CHI TIẾT (reference — line đã cập nhật cho commit 451c40f + fix BUG-13 phiên này)

> Cập nhật từ §8 của 06-23. `redis_server/orchestrator.py` đã dịch ~+35 dòng (BUG-13 thêm restart-loop) và `redis_server/main.py` ~+8 dòng (BUG-20 thêm logic preserve retry_count). `Dashboard/app.py` và `workers/fnac/run.py` KHÔNG đổi → line cũ vẫn đúng. ⚠️ = bug đang mở · ✅ = đã fix.

### 8.1 Trách nhiệm từng file — không đổi so với 06-23 (xem §8.1 ở đó).

### 8.2 Đường đi 1 job (happy path) — line đã cập nhật
```
1. Client POST /api/submit-job                                       app.py:748
   - domain = ret_key.split('_',2)[1] (URL chỉ fallback)            app.py:789-793  ⚠️BUG-51
   - set job_state='queued' (ex=86400, KHÔNG có retry_count)        app.py:809-817  ⚠️BUG-60
   - queue.enqueue('main.crawl_job', url,domain,ret_key,proxy_type, app.py:820-828
                   job_timeout=JOB_TIMEOUT_{DOMAIN}, job_id=ret_key)
   - return 202                                                     app.py:832-840

2. Orchestrator start_orchestrator()                                 orchestrator.py:284
   - _wait_for_redis() (retry 30×2s)                                orchestrator.py:271 (gọi 286)
   - discover_worker_domains() = workers/*/ có Dockerfile           orchestrator.py:79-94  ⚠️BUG-59 (Path(__file__).parent @81)
   - cleanup_stale_workers(domains)                                 orchestrator.py:246 (gọi 299)
     → wipe rq:worker:* (251-256) + slots:* (261-266) → _retry_stale_jobs (268)
   - spawn get_max_concurrent(domain) threads/domain                orchestrator.py:303-314
     mỗi thread = start_worker_for_domain (97-140, ✅BUG-13 restart-on-return + delete stale key @117)

3. ThreadSafeWorker.dequeue_job_and_maintain_ttl                     orchestrator.py:60-76
   - try: _can_acquire_slots(domain) (24-39, fail-closed) ;          heartbeat @68 INSIDE try (✅BUG-13)
     except: backoff 5→10→20→40→60s @71-74

4. crawl_job(url, domain, ret_key, proxy_type)                       main.py:78
   - _set_job_state 'queued' (preserve retry_count 57-62)           main.py:82  (✅BUG-20)
   - _acquire_slot('global','total',TOTAL) Lua INCR                 main.py:85 (Lua 17-27); timeout-fail 88
   - _acquire_slot('domain',domain,max)                             main.py:95; timeout-fail 98
   - _set_job_state 'running'                                       main.py:102  ⚠️BUG-55
   - result = _spawn_and_wait_container(...)                        main.py:106
   - _clear_job_state(ret_key)                                      main.py:107  ⚠️BUG-44 (không ở finally)
   - except (110-118): setex result 116 + clear 117 + raise 118     ✅BUG-15 (wrap caller)
   - finally: release domain (119-121), global (122-124)

5. _spawn_and_wait_container                                         main.py:127
   - ensure image (load tar.gz nếu thiếu)                           main.py:129-145
       cache_file relative @134 ; thiếu cache → result failed+clear 141-145  ✅BUG-14
   - volumes: CHROMIUM_SNAP_DIR ro (KHÔNG isdir)                    main.py:147-149  ⚠️BUG-50
              PROXY_HOST_DIR→/app/Proxy ro nếu isdir(PROXY_CHECK)   main.py:153-158  ✅BUG-42/47
   - containers.run(detach, remove, mem,shm, SYS_ADMIN; KHÔNG name) main.py:160-179  ⚠️BUG-23/34
   - container.wait(timeout=get_job_timeout(domain))                main.py:181  ⚠️BUG-21 (bỏ StatusCode)
   - except wait (183-195): kill 186 + setex result 194            ⚠️BUG-19 (đè good result)
   - đọc result:{ret_key}; setdefault timestamp/domain/url + setex  main.py:197-204  ✅BUG-24
   - no-result fallback                                            main.py:206-211

6. Worker container run.py (fnac/newark giống nhau)                  fnac/run.py:11
   - process_single_request → crawl                                run.py:26 → sourceCode/main.py:17
   - r.setex result:{ret_key} (TTL RESULT_TTL=3600)                run.py:44   ⚠️BUG-22 (ngoài try)

7. Client poll GET /api/job/{ret_key}                               app.py:480-491
```

### 8.3 Redis keys (cập nhật)
| Key | TTL | Ai ghi | Ai xóa |
|---|---|---|---|
| `job_state:{ret_key}` | 86400 | app.py:817 (submit, **KHÔNG retry_count** ⚠️BUG-60) / main.py:63 `_set_job_state` (preserve retry_count) / orchestrator.py:226 (retry, +1) | main.py:74 `_clear_job_state` (gọi 89/99/107/117/144), recovery 211 |
| `result:{ret_key}` | **3600 thường, NHƯNG 86400 cho give-up** ⚠️ | worker run.py:44; main.py 88/98/116/143/194/203/211; **app.py:853** (enqueue fail); **orchestrator.py:218** (give-up, ttl 86400) | dashboard clear, TTL |
| `slots:global:total` / `slots:domain:{d}` | 3600 (EXPIRE mỗi INCR) | Lua INCR (main.py:22) | DECR (main.py:49), cleanup wipe (orchestrator.py:261-266) |
| `rq:queue:crawler:{d}`, `rq:job:*`, `rq:worker:*`, `rq:failed:*` | RQ internal (**failed=1 năm** ⚠️BUG-26) | RQ | cleanup chỉ xóa `rq:worker:*` (251-256) |

**Cảnh báo**: set `rq:queues` chứa **full key** `rq:queue:crawler:{d}` → ⚠️BUG-48 (clear_state double-prefix). `job_id==ret_key` ở mọi nơi.

### 8.4 Data contract — result dict (cập nhật theo BUG-24/49)
- **fnac**: `HtmlFetchResult.to_dict()` ([extractor.py:31-41](../workers/fnac/sourceCode/extractor.py#L31)) + `process_single_request` thêm `ret_key,total_elapsed_seconds,mode,proxy_type,log` (fnac/main.py:58-63). Classify: ✅BUG-49 — 403/429/503 + `code==0`/`>=400` → failed; **band 3xx lọt** ⚠️BUG-64; **200-with-block lọt** (raw §4).
- **newark**: dict literal; `http_code=response_data['status']` ([extractor.py:312](../workers/newark/sourceCode/extractor.py#L312)) thường 0; `main.py:43` success theo html-truthiness ⚠️BUG-53. Browser lifecycle ⚠️BUG-52/58. Bỏ qua `PROXY_DIR` ⚠️BUG-63.
- **Backfill**: main.py read-back (199-203) nay thêm `domain`+`url`+`timestamp` ✅BUG-24. Worker-layer vẫn thiếu `domain`/`timestamp` top-level (đúng — orchestrator backfill).
- Dashboard classify `status=='success'`→finished, khác→failed ([app.py:169](../Dashboard/app.py#L169), [269](../Dashboard/app.py#L269)) — passthrough trung thực (xem §5).

### 8.5 Concurrency model — KHÔNG đổi (xem §1.5 của 06-19). Bổ sung: dequeue override (60-76) nay có backoff; restart-loop (97-140) restart trên mọi work()-return.

### 8.6 Crash recovery — CẬP NHẬT (BUG-20 ĐÃ FIX)
`_retry_stale_jobs` ([orchestrator.py:143-243](../redis_server/orchestrator.py#L143)): scan `job_state:*`, state queued/running, không có result:
- có `result:{ret_key}` → xóa state, skip (181-184)
- RQ `queued` → skip giữ (190-192) · `finished` → xóa state, skip (193-196)
- RQ `failed` (197-202) / trạng thái khác (203-207) / `NoSuchJobError` (208-209) → xóa RQ job + fall-through re-enqueue ✅BUG-20
- xóa job_state (211); nếu `retry_count>=3` → ghi result failed vĩnh viễn ttl **86400** (213-221); ngược lại `q.enqueue(... job_id=ret_key)` (223-225) + setex job_state `retry_count+1` (226-234)
- `_set_job_state` (main.py:54-71) **preserve** retry_count ⟹ cap không bị reset bởi worker — NHƯNG **dashboard submit reset** ⚠️BUG-60.
Persistence: Redis AOF (`--appendonly yes`) + docker volume.
