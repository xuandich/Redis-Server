# BUG-107_LOW_amazon_fr: batch `main()` gọi `process_single_request(url, proxies)` sai chữ ký (2 arg vs 1 dict) → TypeError; dead-code trong container

**Severity**: LOW  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

`process_single_request(request: Dict)` nhận **1 tham số dict** (main.py:58), nhưng đường batch `main()` gọi `await process_single_request(url, proxies)` với **2 tham số vị trí** (main.py:126) → `TypeError` ngay khi chạy standalone. Không nổ trong container (CMD=`python run.py`, và run.py gọi đúng `process_single_request(request)`), nên là dead-code/latent-crash.

## Details

**Location**: workers/amazon_fr/sourceCode/main.py:58 (`async def process_single_request(request: Dict[str, Any])`) vs :126 (`result = await process_single_request(url, proxies)`) ; workers/amazon_fr/Dockerfile:31 (`CMD ["python", "run.py"]`) ; run.py:44 (gọi đúng 1 dict)

**Description**:
Chữ ký hàm đã đổi sang interface Redis (nhận `request` dict, đọc `request.get('url')/'ret_key'/'proxy_type'`) nhưng đường batch CLI `main()` (:110-132) chưa cập nhật — vẫn truyền `(url, proxies)` kiểu cũ (:126). Nếu ai chạy `python sourceCode/main.py` để batch từ Excel, sẽ nổ `TypeError: process_single_request() takes 1 positional argument but 2 were given`. Ngoài ra `read_urls`/`save_results`/`load_proxies_from_excel` cũng chỉ phục vụ đường batch này.

**Why Real**:
Đường container KHÔNG chạm (Dockerfile CMD=run.py → run.py:44 gọi đúng 1 dict) nên KHÔNG ảnh hưởng production worker. Nhưng là latent crash thật trong file được ship, mã batch CLI đã hỏng silently. LOW/dead-code (cùng lớp các bug dead-code như BUG-45), nên vá hoặc xóa để tránh gây hiểu nhầm.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: low  
**reason**: Xác minh: def :58 nhận 1 dict; call :126 truyền 2 arg. Dockerfile:31 CMD=run.py → batch main() không reachable trong container. Latent crash chỉ ở CLI standalone → LOW/dead-code. is_new: file amazon_fr mới, chưa từng audit.

## Impact

- Domain: amazon-config-schema-deploy (completeness-critic gap)
- Source: P4 (completeness-critic)
