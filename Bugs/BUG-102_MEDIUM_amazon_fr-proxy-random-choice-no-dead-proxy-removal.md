# BUG-102_MEDIUM_amazon_fr: proxy chọn `random.choice` mỗi attempt, không loại proxy chết → 1 proxy hỏng ngốn hết retry budget

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

Mỗi attempt trong `fetch_url` chọn proxy bằng `random.choice(self.proxies)` mà không loại bỏ proxy vừa thất bại. Với pool nhỏ (hoặc trùng lặp), cùng một proxy chết có thể được chọn lại nhiều lần → phí các lần retry và tăng khả năng cạn `MAX_RETRIES=5` mà không đổi được sang proxy tốt.

## Details

**Location**: workers/amazon_fr/sourceCode/extractor.py:328 (`proxy = random.choice(self.proxies) if self.proxies else None`) trong vòng `for attempt_idx in range(max_retries)` (:327)

**Description**:
Vòng retry (:327-377) mỗi lần lặp gọi `random.choice(self.proxies)` (:328) — lấy mẫu **có hoàn lại**, không theo dõi proxy nào đã fail. Khi `_start_browser`/`_check_proxy_country` fail hoặc bị block, code `continue` sang attempt kế nhưng lại `random.choice` từ **toàn bộ** pool → có thể chọn trúng lại đúng proxy vừa hỏng. Không có cơ chế `self.proxies.remove(proxy)` hay rotation tuần tự.

**Why Real**:
Compound với BUG-100 (timeout): retry lãng phí vào proxy chết vừa tốn thời gian (đẩy tổng thời gian gần/vượt 300s) vừa làm job thất bại dù pool vẫn còn proxy tốt chưa thử. Cùng cơ chế BUG-87 (orchestra) nhưng ở file amazon_fr mới.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: survives_escalation=true. dup_guess=BUG-87 nhưng BUG-87 ở worker orchestra/file khác; amazon_fr là file mới → is_new=true. Medium vì hiệu ứng phụ thuộc kích thước pool proxy, nhưng khuếch đại trực tiếp BUG-100.

## Impact

- Domain: amazon-crawl-logic
- Source: P4 (survives_escalation=true)
