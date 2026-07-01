# Code Review — Flow Audit (2026-07-01): AUDIT worker MỚI `amazon_fr` + Dashboard routing + regression sweep

**Commit nền**: `57ec6b4` (HEAD). **Diff audit từ**: `ef7e652` (nền chu trình 06-29) → HEAD: **amazon_fr worker MỚI ~822 dòng** (thêm ở `ceee225`, extractor sửa ở `1cc22f3` SAU audit 06-29), Dashboard/app.py routing ~55 dòng, orchestrator +1 dòng.
**Phương pháp**: 1 Workflow toàn diện `find → adversarial verify → escalate → completeness-critic` (9 dimension, 5 dành cho amazon_fr). 51 agent, 37 finding → verify. Đợt đầu bị session-limit ở 9 agent (verify/escalate/completeness) → **resume same-session** cache-hit 41 agent, chạy nốt 10. Maintainer đọc lại code thật để adjudicate các finding tranh chấp (nhất là resource-leak).

> Nối tiếp [2026-06-27b](2026-06-27b_flow-audit.md) và chu trình 06-29 (BUG-82..98). Chu trình này nhắm **code chưa từng audit**: worker `amazon_fr` (06-29 chỉ audit manomano/orchestra) + thay đổi Dashboard routing.

---

## 1. Kết quả: 9 bug MỚI (BUG-99 → BUG-107) — 1 HIGH · 3 MEDIUM · 5 LOW

37 finding → 21 confirmedFinal (đều survives_escalation=true) → dedup còn **9 bug khác biệt** (nhiều dimension tìm ra cùng 1 defect):

| Bug | Sev | Cơ chế | file:line |
|---|---|---|---|
| **BUG-99** | **HIGH** | **False-success**: `page.goto()` vứt Response → HTTP status không bao giờ kiểm; `mark_success(...,200,...)` hardcode; success chỉ dựa DOM `#title` → 403/429/503/404 của Amazon vẫn `status=success`. Lệch chuẩn fnac (BUG-49). | extractor.py:286,315,366 |
| **BUG-100** | **MED** | `JOB_TIMEOUT_AMAZON_FR=300s` quá ngắn cho `MAX_RETRIES=5` × multi-nav. **Commit `1cc22f3` nâng retries 3→5 làm nặng thêm.** MAX_RETRIES không truyền vào container env → không tunable. Death-penalty giết giữa chừng → false-failure + phí công. | config.py:10; .env:17; main.py:162-171 |
| **BUG-101** | **MED** | Gate `_is_product_page` dùng `#title` generic + `clean_amazon_url` không gọi trên đường Redis → search/category page markable success. | extractor.py:210; main.py:30 vs 79 |
| **BUG-102** | **MED** | Proxy `random.choice` mỗi attempt, không loại proxy chết → 1 proxy hỏng ngốn hết retry budget (compound BUG-100). | extractor.py:328 |
| **BUG-103** | **LOW** | Response headers lấy từ sub-resource amazon-200 bất kỳ (last-wins), không phải document sản phẩm → metadata sai. | extractor.py:240-242 |
| **BUG-104** | **LOW** | 3 site tạo context/browser ngoài try/finally trên đường lỗi (`_check_proxy_country`, `_navigate_and_extract`, `_start_browser` return False). **Bounded** bởi `browser.close()` attempt kế → LOW (5 verifier bác mức HIGH là đúng). | extractor.py:89,100-112,219-258 |
| **BUG-105** | **LOW** | `_check_proxy_country` không hề so country_code với 'FR' → luôn True; geo chỉ dựa postal-in-HTML. Hàm không làm đúng tên/docstring. | extractor.py:97-112 |
| **BUG-106** | **LOW** | Dashboard `_extract_domain_from_url` substring match không ranh giới nhãn → `notfnac.com`/`amazon.fr.x.com` mis-route tới worker thật (khác góc BUG-81). | Dashboard/app.py:728-745 |
| **BUG-107** | **LOW** | Batch `main()` gọi `process_single_request(url, proxies)` sai chữ ký (2 arg vs 1 dict) → TypeError; dead-code trong container (CMD=run.py). | main.py:126 vs 58 |

**Điểm nhấn**: BUG-99 là bug HIGH thật — maintainer tự đọc `extractor.py` xác nhận từng dòng, không chỉ dựa phiếu agent. Cùng lớp false-success đã vá cho fnac (BUG-49/64/65) nay **tái phát trong file amazon_fr mới**. BUG-100 đáng chú ý ở tính mỉa mai: commit "improve reliability" (`1cc22f3`) nâng `MAX_RETRIES` 3→5 lại **làm trầm trọng** nguy cơ timeout vì `JOB_TIMEOUT` không đổi.

## 2. Verify fix cũ (regression) — sạch

- **BUG-81**: STATE 06-29 nghi fix MISSING. **Kiểm lại: fix ĐÃ CÓ và ĐÚNG** — `Dashboard/app.py:724 _extract_domain_from_url` dùng `urlparse` + strip port + match pattern. Rename `(FIXED)` là chính đáng; cờ "MISSING" trong STATE là **lỗi thời** (fix đã vào ở `ceee225`/`641a10c`). *(Góc substring-no-boundary còn lại → tách thành BUG-106 mới, không phải regression của BUG-81.)*
- **BUG-46** (dead amazon config): nay đã có worker amazon_fr; `.env` có `MAX_CONCURRENT_AMAZON_FR=3`, `JOB_TIMEOUT_AMAZON_FR=300`, và `orchestrator` dùng `get_max_concurrent('amazon_fr')` → config "amazon" đã được nối. *(Còn hằng `redis_server/config.py:37 MAX_CONCURRENT_AMAZON` đọc env `MAX_CONCURRENT_AMAZON` không tồn tại → hằng chết/misleading, lớp BUG-45 — nit, chưa file.)*
- Dashboard 55-dòng diff không phá BUG-60/48/43.
- orchestrator +1 dòng (`redis_client.set('system:supported_domains', ...)`) là cơ chế hậu thuẫn validate BUG-16 — benign.

## 3. REFUTED / non-new đáng ghi

- **Multi-domain overcommit** (5 domain × 3 = 15 > MAX_CONCURRENT_TOTAL=10): Lua global gate chặn ở 10, thread dư idle — không hại (đã refuted 06-27b, vẫn đúng).
- **Context-leak HIGH claim** (BUG-104): 5 verifier bác mức HIGH — đúng, vì `browser.close()` thu hồi. Giữ LOW.
- **`_start_browser` không đóng khi False**: gộp vào BUG-104 (cùng lớp bounded-leak).
- **tar.gz trong build context** / **requirements unpinned** / **docker_client 240s < wait 300s**: real nhưng dup (họ BUG-79/BUG-76/BUG-41).

## 4. Completeness-critic gaps (theo dõi, chưa file)

1. `_change_delivery_address` trả `False` ở nhánh except (:158) nhưng caller chỉ kiểm `is None` (:281) → đường False đi tiếp như đã đổi địa chỉ; **bù đắp** bởi postal-in-HTML (:306). Nit control-flow.
2. Xvfb/`headless:False` chỉ có ở amazon_fr (khác cả fleet) — cần kiểm `CHROMIUM_PATH` khớp binary trong image (probe deploy, chưa xác nhận là bug).
3. Dashboard list/monitor views có thể bỏ field riêng của amazon_fr (`proxy_used`, `country`, `log`) — cùng lớp BUG-72/BUG-68 (dup).

## 5. Khuyến nghị ưu tiên

1. **BUG-99 (HIGH)** — đọc `response.status` của `goto(url)` (:286), truyền vào `mark_success`, và gate 403/429/503/`==0`/`>=400` → `mark_failed` như fnac. Đây là bug ảnh hưởng chất lượng dữ liệu nghiêm trọng nhất.
2. **BUG-100 (MED)** — nâng `JOB_TIMEOUT_AMAZON_FR` (≥600s như newark) HOẶC hạ/expose `MAX_RETRIES` qua container env; cân nhắc revert phần 3→5 của `1cc22f3` nếu không nâng timeout.
3. **BUG-101/102 (MED)** — thắt gate product (ưu tiên `#productTitle`/`#dp` path-marker, normalize URL trên đường Redis) + rotation proxy loại-dần.
4. **LOW** (103/104/105/106/107) — dọn khi tiện; BUG-107 chỉ cần sửa/xóa batch `main()`.

## 6. Trạng thái tồn từ trước (chưa fix)

BUG-91 (HIGH heartbeat SimpleWorker — áp dụng cả amazon_fr job 300s), BUG-84/88 (render-guard/dead-code manomano/orchestra), BUG-77 (pubsub leak), BUG-74/69 (nếu chưa vá) vẫn OPEN — không thuộc phạm vi diff amazon_fr đợt này.
