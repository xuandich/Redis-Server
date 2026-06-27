# Code Review — Flow Audit (2026-06-27b): RE-AUDIT TOÀN DIỆN pha 1→5 (logic chunked mới)

**Commit nền**: `16438da`. **Phương pháp**: re-audit chuẩn pha 1→5 dùng harness đã harden (guard cỡ-mẻ: P4≤3 dim, P5≤6 finding; tách find/verify; checkpoint STATE.md). Pha 6 skip (workers/ không đổi từ 06-27).
**Quy mô**: P1 (6 agent) · P2 (3 nhóm/23 bug) · P3 (3 area) · P4 (8 dim, 3 batch, ~33 finding) · P5 (11 finding, 2 mẻ). Tất cả pha chạy **song song theo wave** — không pha nào chạm session-limit (validate logic mới ✅).

> Nối tiếp [2026-06-27](2026-06-27_flow-audit.md). Đây là vòng re-audit "từ đầu" toàn hệ (fnac/newark/orchestrator/dashboard), KHÁC 06-27 (chỉ 2 worker mới).

---

## 1. Pha 1 — Verify fixes: 6/6 ĐÚNG, 0 regression ✅

BUG-13, BUG-60, BUG-61, BUG-20, BUG-24, BUG-49 — tất cả `fix_present=true, fix_correct=true`, regression_risk none/low. Vài nit:
- **BUG-20**: cap thực ra cho phép **4 lần thực thi** (1 gốc + 3 retry), log "attempt/3" gây hiểu nhầm. Phạm vi cứu hẹp hơn mô tả (except trong crawl_job đã ghi result cho phần lớn exception).
- **BUG-61**: doc/§4 ghi commit `e921233` nhưng fix thật ở `e7fa426` (chỉ sai truy vết).
- **/api/cancel** chỉ xóa result, không cancel RQ → recovery có thể re-enqueue job vừa hủy (tương tác BUG-20).

## 2. Pha 2 — Reconcile 23 bug OPEN: 21 open / 1 partial / 1 fixed

- **BUG-23** → **PARTIALLY-FIXED**: `stop.sh:42-47` đã dọn container theo network (sub-claim stop.sh hết hiệu lực), NHƯNG lõi vẫn open (`containers.run` không name/labels [main.py:160-179], cleanup không kill container).
- 21 bug còn nguyên cơ chế (16,17,19,28,29,30,31,32,33,34,48,51,52,53,55,56,57,58...) — chỉ lệch line.
- **BUG-29** xác nhận thật: `decode_responses=True` nhưng lookup bytes-key `b'description'` ([app.py:141](../Dashboard/app.py#L141)) → URL queued luôn 'N/A'.

## 3. Pha 3 — Flow accuracy: logic ĐÚNG, chỉ BUG-60 lỗi thời

Flow map §8.2/§8.3/§8.6 của review 06-26 còn khớp **logic** đến từng nhánh. Khác biệt **duy nhất**: **BUG-60 nay đã FIXED** ([app.py:808-829](../Dashboard/app.py#L808) preserve retry_count) — review cũ vẫn ghi OPEN ⚠️. Hệ quả line-shift +12 ở app.py (enqueue→832-840, return 202→844-852). orchestrator.py/main.py/run.py không đổi.

→ **Hành động**: nên rename `Bugs/BUG-60*` → `(FIXED)` + cập nhật §4 (BUG-60 đã có trong §4 là fixed, nhưng file bug chưa rename).

## 4. Pha 4+5 — Find→Verify: 4 bug MỚI (BUG-77→80)

33 finding → lọc 24 trùng bug cũ + 8 new-candidate + 3 borderline → verify 11 → **4 confirmed-new**:

| Bug | Sev | Cơ chế |
|---|---|---|
| **BUG-77** | **MEDIUM** | Redis blip lúc teardown rò **PubSubWorkerThread + connection** mỗi restart (register_death raise trước unsubscribe → skip). Chỉ lộ do restart-loop BUG-13; khác BUG-61. |
| BUG-78 | LOW | manomano/orchestra orphan Chrome khi `uc.Chrome()` raise giữa init (no process ref → no quit). Bounded bởi 1-job-1-container. |
| BUG-79 | LOW | Cache `.tar.gz` 421MB nằm TRONG build context + thiếu `.dockerignore` → ship 402MB context mỗi build worker. |
| BUG-80 | LOW | Dashboard `logs/` path tương đối theo CWD ([app.py:20-24](../Dashboard/app.py#L20)) — fragile import-time. |

### Bị REFUTED / không-mới (đáng ghi)

- **Stale give-up result drop job** (HIGH claim): `is_real=true` NHƯNG `is_new=false` — verifier xếp vào họ BUG-67. ⚠️ Cơ chế data-loss (recovery dùng result give-up TTL 86400 làm bằng chứng "đã xong" → drop job re-submit) đáng theo dõi dù không file mới.
- **_set_job_state lost-update** (read-modify-write non-atomic): real nhưng not-new (họ BUG-60).
- **REFUTED thật** (đọc kỹ layout container): `/api/delete+cancel orphan` (delete đúng chủ đích), `multi-domain overcommit 14>10` (Lua global gate chặn ở 10, thread dư idle — không hại), `autoload cache_file CWD` (WORKDIR /app khóa CWD trong container), `recovery enqueue-order`, `slot-wait stop` (LOW latent).

## 5. Khuyến nghị ưu tiên

1. **BUG-77 (MEDIUM)** — dọn pubsub thread cũ trước restart (giữ ref + `unsubscribe()` best-effort).
2. Rename `BUG-60*` → `(FIXED)` (xác nhận P1+P3).
3. BUG-78/79/80 LOW — dọn khi tiện (`.dockerignore`, neo `__file__` cho logs).
4. Từ 06-27a còn OPEN: **BUG-74 (HIGH timeout)**, **BUG-69 (HIGH manomano false-success)** — chưa fix.

## 6. Validate logic harness mới ✅

Toàn bộ re-audit chạy bằng nhiều `Workflow()` nhỏ song song; **không lần nào chạm session-limit giữa chừng**. Mỗi pha checkpoint ra `results/` + STATE.md. P4-b1 từng mất output-file (task cleanup) → **resume cache tức thì khôi phục** (0 token). Kết luận: guard cỡ-mẻ + tách pha + checkpoint hoạt động đúng thiết kế.
