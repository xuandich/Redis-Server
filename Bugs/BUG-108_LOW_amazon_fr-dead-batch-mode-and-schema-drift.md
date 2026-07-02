# BUG-108_LOW_amazon_fr: batch-mode chết (read_urls/save_results/main/__main__) + result schema lệch chuẩn (country/proxy_used thừa trong to_dict)

**Severity**: LOW  
**Status**: OPEN  
**Date Found**: 2026-07-02  

## Summary

`workers/amazon_fr` mang 2 tàn dư không ảnh hưởng correctness nhưng lệch chuẩn so với các worker Redis-thuần khác (manomano, orchestra): (1) toàn bộ chế độ batch-Excel-CSV (`read_urls`/`save_results`/`main()`/`__main__` + `INPUT_FILE`/`OUTPUT_DIR`/`MAX_URLS` trong config) không bao giờ chạy trong container; (2) `models.py.to_dict()` xuất thêm 2 field ngoài schema canonical (`country` luôn `None`, `proxy_used` mà fnac/manomano track nội bộ nhưng không xuất).

## Details

**Location**:
- `workers/amazon_fr/sourceCode/main.py:1-5` (docstring "Batch processor"), `:21-34` (`read_urls`), `:37-55` (`save_results`), `:110-136` (`main()` + `__main__`)
- `workers/amazon_fr/sourceCode/config.py:7-8,11` (`INPUT_FILE`, `OUTPUT_DIR`, `MAX_URLS`)
- `workers/amazon_fr/sourceCode/models.py:13,17` (`self.country`, `self.proxy_used` trong `__init__`), `:26,30` (2 key tương ứng trong `to_dict()`)
- Đối chứng: `workers/manomano/sourceCode/main.py` (chỉ có `process_single_request`, không batch mode), `workers/manomano/sourceCode/models.py` (`to_dict()` không có `country`/`proxy_used` dù class có track `proxy_used`)

**Description**:

1. **Batch mode chết**: `Dockerfile:31 CMD ["python", "run.py"]` — `run.py` chỉ import `process_single_request` từ `main.py` (không đụng `read_urls`/`save_results`/`main()`). Cùng cơ chế đã xác nhận ở BUG-107 (batch `main()` gọi sai chữ ký) — nhưng BUG-107 chỉ vá triệu chứng (chữ ký sai), còn cả khối chức năng batch vẫn là dead-code trong context container. `manomano`/`orchestra` (2 worker được viết mới nhất, sạch nhất hệ thống) không hề mang cấu trúc này — xác nhận đây là tàn dư từ bản scraper Excel độc lập trước khi tích hợp Redis, chưa được dọn khi port sang kiến trúc worker.

2. **Schema lệch chuẩn**: Canonical schema (xác nhận qua fnac + manomano, khớp `00-context.md §5`): `to_dict()` chỉ xuất `{url, html, headers, http_code, cookies, elapsed_ms, error, status}` (8 field); `main.py` add thêm `{ret_key, proxy_type, total_elapsed_seconds, log}` (+ field riêng domain nếu có, vd fnac có `mode`). `amazon_fr.models.py.to_dict()` xuất thêm `country` (`self.country` không bao giờ được set qua `mark_success`/`mark_failed` → luôn `None`; `main.py:85 result_dict['country'] = AMAZON_COUNTRY` ghi đè lại post-hoc → field tồn tại trong class hoàn toàn vô nghĩa) và `proxy_used` (fnac có `proxy_used`/`proxy_country` track nội bộ y hệt nhưng **không** đưa vào `to_dict()`).

**Why Real**:
Không gây lỗi chức năng (container chỉ dùng `process_single_request`; field thừa trong JSON output vô hại với downstream vì Dashboard đọc theo key cụ thể, dư field không phá gì) — nhưng là dead-code + thiết kế không nhất quán, gây khó bảo trì (dev đọc `main.py` tưởng batch mode là đường chạy chính do docstring ghi "Batch processor", trong khi thực tế toàn bộ nhánh đó chưa từng thực thi trong production). Phát hiện khi port sang `amazon_uk` (worker mới, dọn sạch cả 2 điểm này ngay lúc viết) và so sánh ngược lại với `amazon_fr` gốc.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: low  
**reason**: Xác minh trực tiếp qua đọc code (không qua pipeline find→verify tự động) — đối chứng `manomano/sourceCode/{main,models}.py` làm baseline "sạch". Không phải regression của BUG-99..107 (khác cơ chế: đây là dead-code/schema-drift, không phải false-success/leak/timeout). LOW vì không ảnh hưởng hành vi runtime thật.

## Impact

- Domain: amazon-config-schema-deploy / code-cleanliness
- Source: Maintainer review khi port amazon_fr → amazon_uk (2026-07-02), đối chứng manomano/fnac
