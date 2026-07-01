# BUG-104_LOW_amazon_fr: context/browser tạo ngoài try/finally trên đường proxy-failure → leak window (bounded bởi browser.close)

**Severity**: LOW  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

Ba điểm dọn-dẹp không đầy đủ trên đường lỗi: (1) `_check_proxy_country` tạo context/page rồi chỉ `close` ở happy-path — raise giữa chừng thì leak; (2) `_navigate_and_extract` tạo context + route + `add_init_script` NGOÀI `try/finally`; (3) `_start_browser` trả False khi proxy-check fail mà không đóng browser/playwright/display. **Tất cả bounded** — `_start_browser` của attempt kế (hoặc `close_browser()` cuối job) đóng browser cũ và thu hồi mọi context → severity LOW.

## Details

**Location**: workers/amazon_fr/sourceCode/extractor.py:100-104 (`_check_proxy_country` close chỉ happy-path, except :110-112 không finally) ; :219-258 (context/page/route/add_init_script trước `try:` ở :260, `finally: await context.close()` ở :321-322) ; :48-91 (`_start_browser` return False ở :90 không đóng browser)

**Description**:
1. `_check_proxy_country` (:97-112): `context = await self._browser.new_context()` (:100), `page=...` (:101), `goto('https://ipwho.is/')` (:102), `data=await response.json()` (:103), `await context.close()` (:104). Nếu :102/:103 raise → `except` (:110-112) return False **không đóng context**.
2. `_navigate_and_extract` (:216-322): `context = await self._browser.new_context(...)` (:219), `page=await context.new_page()` (:227), `await page.route(...)` (:236), `await page.add_init_script(...)` (:246). Các câu này ở **trước** `try:` (:260) mà `finally` (:321-322) mới `close`. Nếu `new_page`/`route`/`add_init_script` raise → context leak.
3. `_start_browser` (:48-91): khi `_check_proxy_country()` False → `return False` (:89-90) mà không đóng `self._browser`/`self._playwright`/`self._display`.

**Why Real (nhưng LOW — bounded)**:
Mỗi attempt kế trong `fetch_url` gọi lại `_start_browser` (:332) → :52-57 `await self._browser.close()` + `self._playwright.stop()` (đóng cả context leak). Attempt cuối: `main.py:107 finally: await fetcher.close_browser()`. Vì 1-job-1-container và browser luôn bị đóng ở ranh giới attempt/job, tối đa 1 context/browser lơ lửng trong thời gian ngắn, luôn được thu hồi. Đây chính là lý do nhiều verifier bác bỏ mức HIGH — đúng. Vẫn là code-smell thật (thiếu try/finally) cùng lớp BUG-97/BUG-98 nhưng đã được browser.close che chắn.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: low  
**reason**: survives_escalation=true (nhiều dimension). Xác minh thủ công (đọc code): leak có thật nhưng bounded bởi `_start_browser` :52-54 và `close_browser` main.py:107. dup_guess=BUG-97/BUG-98 (manomano/orchestra, file khác); amazon_fr file mới → is_new=true. Hạ về LOW so với claim HIGH ban đầu vì cơ chế thu hồi tồn tại.

## Impact

- Domain: amazon-resource-leaks
- Source: P4 (gộp 3 site cùng lớp: _check_proxy_country + _navigate_and_extract + _start_browser)
