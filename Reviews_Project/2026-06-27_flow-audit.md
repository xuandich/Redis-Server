# Code Review — Flow Audit (2026-06-27): 2 worker MỚI manomano + orchestra

**Commit nền**: `af485af` (branch `main`). **Trọng tâm**: audit 2 worker **chưa từng review** — `manomano` (4a8eb95) và `orchestra` (bf477ae) — vừa landed sau chu trình 06-26.
**Phương pháp**: Workflow tổng hợp — Pha 6 worker-correctness (manomano+orchestra) + Pha 4 find scoped 6 dimension tích hợp → pipeline Pha 5 adversarial verify. **Lần chính: 34 agent, 26 finding verify (13 confirmed / 13 bác-hoặc-trùng / 7 needs-runtime); 4 agent chết connection.** + Gap-fill (config-deploy finder chết + 2 NULL verdict): finder OK nhưng 7 verify chết session-limit → **resume hôm sau** (8 agent) → 2 confirmed LOW.

> Nối tiếp [2026-06-26](2026-06-26_flow-audit.md). 2 worker mới dùng **undetected_chromedriver + Selenium + Xvfb + Chrome trong-image** (KHÁC Playwright + snap-mount của fnac/newark) → bề mặt lỗi mới hẳn.

---

## 1. Tổng kết — 8 bug mới (BUG-69 → BUG-76)

| Bug | Sev | Worker | Cơ chế |
|---|---|---|---|
| **BUG-69** | **HIGH** | manomano | False-success: KHÔNG soi nội dung/sản phẩm/navigation. `not cf_blocked and not empty_page(<1000B)` → mark_success. Không selector/parse/redirect-check nào. ([extractor.py:158-196,234-245](../workers/manomano/sourceCode/extractor.py#L158)) |
| **BUG-70** | MEDIUM | orchestra | False-success: title/price trích rỗng (`_extract_product_info` nuốt except → "") vẫn mark_success. ([extractor.py:153-182,270-273](../workers/orchestra/sourceCode/extractor.py#L153)) |
| **BUG-71** | LOW | cả 2 | `http_code` hardcode literal `200` trong mark_success — Selenium không đo status thật → metadata bịa. ([manomano:245](../workers/manomano/sourceCode/extractor.py#L245) / [orchestra:273](../workers/orchestra/sourceCode/extractor.py#L273)) |
| **BUG-72** | LOW | orchestra | title/price ghi vào result nhưng mọi view list/grouped/stats của Dashboard bỏ qua — chỉ thấy ở raw JSON. ([app.py:174-184,257-268](../Dashboard/app.py#L174)) |
| **BUG-73** | LOW | cả 2 | `_create_proxy_auth_extension` rò `/tmp/proxy_ext_*` khi exception sau mkdtemp (except không rmtree). Giới hạn trong vòng đời container. ([manomano:51-63](../workers/manomano/sourceCode/extractor.py#L51)) |
| **BUG-74** | **HIGH** | cả 2 | Thiếu `JOB_TIMEOUT_{MANOMANO,ORCHESTRA}` → `container.wait(120s)` ([main.py:181](../redis_server/main.py#L181)) nhưng CF-wait 18×5s=90s + WebDriverWait 20s ≈115s/attempt × 3 → `container.kill()` giết Chrome giữa chừng → fail oan hàng loạt. newark đã có 720s. |
| **BUG-75** | LOW | cả 2 | `.env.example` thiếu `MAX_CONCURRENT_MANOMANO/ORCHESTRA` → `cp .env.example .env` spawn 5 thread/domain thay vì 3 (bị TOTAL=10 cắt nên nhẹ). Họ BUG-66. |
| **BUG-76** | LOW | cả 2 | requirements.txt toàn `>=` + `google-chrome-stable` không pin → build không tái lập; mismatch Chrome/uc fail lúc build. Họ BUG-54. |

**Chủ đề nổi bật**: cả 2 worker mới đều mắc **false-success** — đánh dấu thành công mà không xác minh đã cào ĐÚNG dữ liệu (cùng họ BUG-49/53/65 nhưng cơ chế khác: thiếu CẢ http_code-gate LẪN content-validation). + lỗi cấu hình vận hành (BUG-74 timeout là nghiêm trọng nhất về mặt "chạy được hay không").

---

## 2. Đã verify nhưng KHÔNG mới (trùng bug cũ — không file lại)

- **Slot overcommit** (Σ per-domain 17 > TOTAL 10): real, nhưng Lua global gate ([main.py:93](../redis_server/main.py#L93)) chặn ở 10 → thread dư idle, không overcommit thật. Trùng họ config-chết BUG-45/46.
- **`MAX_CONCURRENT_AMAZON=3` dead** (không có `workers/amazon`): trùng BUG-45/46.
- **`discover_worker_domains` neo `Path(__file__).parent/'workers'`**: real (chỉ chạy đúng trong container), trùng BUG-59/path-after-move (đã ghi 06-26 §1).
- **Chrome path mismatch**: worker mới hardcode `binary_location=/usr/bin/google-chrome` (Chrome trong-image) trong khi orchestrator vẫn inject `CHROMIUM_PATH` + bind-mount `/snap/chromium` vào MỌI container ([main.py:147-149,170](../redis_server/main.py#L147)). Real (mount thừa cho worker mới) nhưng verifier đánh **not-new** (lớp config-mount đã biết). Đáng dọn khi đụng tới mount.

---

## 3. ⚠️ 7 finding cần RUNTIME mới chốt (đọc code không đủ — chạy worker trên HTML thật)

Phần lớn là **selector/parse fragility** — không thể khẳng định đúng/sai nếu không chạy trên DOM thật:

| # | Sev | Vị trí | Nghi vấn |
|---|---|---|---|
| 1 | med | [manomano extractor.py:188-193](../workers/manomano/sourceCode/extractor.py#L188) | CF-block detect chỉ theo substring EN/FR title — block dạng khác lọt |
| 2 | med | [manomano:194](../workers/manomano/sourceCode/extractor.py#L194) | Ngưỡng empty_page <1000B + WebDriverWait>5000B có thể sai cho trang thật |
| 3 | low | [manomano:165-179](../workers/manomano/sourceCode/extractor.py#L165) | Vòng chờ CF 18 lần — hiệu quả pass thực tế? |
| 4 | med | [orchestra:159,203](../workers/orchestra/sourceCode/extractor.py#L159) | Title selector `//h1[@class='product-name']` khớp EXACT class → vỡ nếu thêm class |
| 5 | med | [orchestra:166-179](../workers/orchestra/sourceCode/extractor.py#L166) | Price selector `//*[@class='attributes']//div[contains(...)]` rất mong manh |
| 6 | med | [orchestra:260-266,281-283](../workers/orchestra/sourceCode/extractor.py#L260) | empty_page <1000B; trang block lớn vẫn lọt |
| 7 | low | [orchestra:268](../workers/orchestra/sourceCode/extractor.py#L268) | `get_cookies()` dict-comp không guard key thiếu |

→ **Khuyến nghị**: chạy manomano + orchestra trên vài URL sản phẩm thật + 1 URL chết/redirect (qua `Run_Test/test_api_batch.py`) để xác nhận #1-#6. Liên quan trực tiếp BUG-69/70 (nếu selector vỡ → false-success càng nặng).

---

## 4. Khuyến nghị ưu tiên fix

1. **BUG-74 (HIGH)** — thêm `JOB_TIMEOUT_MANOMANO/ORCHESTRA=720` vào `.env` + `.env.example`. Rẻ, chặn fail oan hàng loạt. Gộp luôn BUG-75.
2. **BUG-69 (HIGH)** — manomano: thêm validation navigation/content trước mark_success.
3. **BUG-70 (MEDIUM)** — orchestra: gate trên title/price rỗng.
4. Còn lại (BUG-71/72/73/76) LOW — dọn khi tiện.
5. Chạy runtime-check (§3) để chốt selector fragility.

---

## 5. Trạng thái harness audit

- Lần chính `wf_a9a28968`: hoàn tất, 4 agent connection-drop đã bù bằng gap-fill.
- Gap-fill `wf_9df58c8f`: verify chết session-limit → **resume thành công hôm sau** (đúng quy trình resume của harness).
- `results/verdicts.json` = kết quả lần chính; `verdicts_2026-06-26.json` = backup chu trình trước.
- Pha 1-3 (verify-fix/reconcile/flow) **không chạy** lần này — trọng tâm là 2 worker mới, code tầng orchestrator/dashboard không đổi từ 06-26.
