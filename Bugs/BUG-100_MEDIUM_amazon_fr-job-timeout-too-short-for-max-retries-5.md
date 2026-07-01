# BUG-100_MEDIUM_amazon_fr: JOB_TIMEOUT_AMAZON_FR=300s quá ngắn cho MAX_RETRIES=5 (commit 1cc22f3 nâng 3→5) → death-penalty giết container giữa chừng

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

`MAX_RETRIES=5` (mặc định, nâng từ 3 ở commit 1cc22f3) với mỗi attempt là 1 chuỗi navigation nặng (goto home 30s + reload 30s×2 + đổi địa chỉ + goto sản phẩm 45s + waits) có thể vượt xa `JOB_TIMEOUT_AMAZON_FR=300s`. Khi vượt, death-penalty / `container.wait` timeout giết container giữa chừng → false-failure + phí toàn bộ công đã làm + có thể kích hoạt crash-recovery re-enqueue (tăng retry_count).

## Details

**Location**: workers/amazon_fr/sourceCode/config.py:10 (`MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '5'))`) ; .env:17 (`JOB_TIMEOUT_AMAZON_FR=300`) ; extractor.py:324-350 (vòng retry + double-navigation trong attempt 'blocked') ; redis_server/main.py:162-171 (env container KHÔNG có MAX_RETRIES), :182,:187 (container.wait/kill theo timeout)

**Description**:
`fetch_url(url, max_retries=5)` (extractor.py:324) lặp tối đa 5 attempt. Mỗi attempt: `_start_browser` (launch chromium ~2-5s + `_check_proxy_country` goto ipwho.is 10s) + `_navigate_and_extract` = goto home (timeout 30s, :262) + reload (30s, có thể reload lần 2 thêm 30s, :266-274) + `_change_delivery_address` (~8s waits, :130-158) + goto sản phẩm (45s, :286) + các `wait_for_timeout` (2-4s). Với nhánh `status=='blocked'` còn navigate LẦN 2 trong cùng attempt (:344-347). Worst-case ~120-140s/attempt × 5 = 300-700s; kể cả case trung bình khi bị CF/postal retry vài lần đã dễ vượt 300s.

`redis_server/main.py:162-171` dựng env cho container KHÔNG truyền `MAX_RETRIES` → không thể hạ retries qua env; giá trị 5 cứng trong image. Khi tổng thời gian vượt `JOB_TIMEOUT_AMAZON_FR=300s`, `container.wait(timeout=...)`/death-penalty (:182,:187) kill container.

**Why Real**:
Amazon bị block/CF/postal-retry là chuyện thường → attempt lặp nhiều lần → thời gian thực dễ chạm/vượt 300s. Container bị kill giữa attempt 4/5 (có thể sắp thành công) → job đánh dấu failed dù chưa cạn retry, phí ~300s, và tương tác crash-recovery (`_retry_stale_jobs`) có thể re-enqueue → tăng `retry_count` tiến gần cap 3 vô ích. **Commit 1cc22f3 ("improve reliability") nâng `MAX_RETRIES` 3→5 nhưng KHÔNG nâng timeout → chính commit cải thiện lại làm bug nặng thêm.**

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: 6 dimension độc lập cùng confirm (1 xếp high "false-failure hàng loạt", 5 xếp medium), tất cả survives_escalation=true. Verify diff `1cc22f3`: `-MAX_RETRIES ... '3'` → `+... '5'` và `fetch_url(max_retries=3)`→`=5`, timeout 300s không đổi. is_new: BUG-96 là orchestra `job_timeout=180s` — worker/file/giá trị khác; đây là amazon_fr (file mới). Severity medium vì đây là bug tuning/config (fix = nâng timeout hoặc hạ/tunable retries), nhưng leo lên HIGH khi Amazon block nặng.

## Impact

- Domain: amazon-integration-orchestrator / worker-resilience / retry-lifecycle
- Source: P4 (6 dimension, survives_escalation=true)
