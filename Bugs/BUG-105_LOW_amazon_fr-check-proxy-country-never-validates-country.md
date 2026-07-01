# BUG-105_LOW_amazon_fr: `_check_proxy_country` không hề kiểm country → luôn trả True với mọi proxy sống (geo chỉ dựa postal-code-in-HTML)

**Severity**: LOW  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

Hàm tên `_check_proxy_country` và docstring nói "Kiểm tra IP thực tế và country", nhưng thực chất chỉ kiểm **liveness** (gọi ipwho.is thành công) → `return True` bất kể `country_code` là gì. Proxy không phải Pháp vẫn qua. Việc ép geo France chỉ còn dựa gián tiếp vào kiểm `AMAZON_POSTAL_CODE not in html` ở downstream.

## Details

**Location**: workers/amazon_fr/sourceCode/extractor.py:97-112 (đặc biệt :105-109 log country rồi :109 `return True`); tương phản downstream :306-309 (`if AMAZON_POSTAL_CODE not in html: return ... 'no_postcode'`)

**Description**:
```
async def _check_proxy_country(self) -> bool:
    """Kiểm tra IP thực tế và country qua proxy đang dùng. Trả False nếu thất bại."""
    try:
        ... response = await page.goto('https://ipwho.is/', ...)
        data = await response.json()
        ...
        ip = data.get('ip','?'); country = data.get('country','?')
        self.add_log(f"🌍 IP: {ip} | {country} ...")
        return True          # <-- không so sánh country_code với 'FR'
    except Exception:
        return False
```
`data.get('country_code')` chỉ dùng để render cờ emoji (:107), không có nhánh `if country_code != 'FR': return False`. Vậy proxy US/DE/... vẫn `return True`. Geo thực sự chỉ được ép ở :306 (postal 75001 phải có trong HTML sau khi `_change_delivery_address`) — mà amazon.fr có thể cho đặt địa chỉ giao 75001 từ IP ngoài Pháp trong một số trường hợp → geo không được đảm bảo ở tầng proxy.

**Why Real**:
Hàm không làm đúng điều tên/docstring hứa (dead geo-check) → gây hiểu nhầm khi bảo trì, và geo-correctness cho pricing amazon.fr chỉ còn dựa 1 lớp postal-in-HTML. LOW vì lớp postal bù đắp phần lớn ca; nhưng là lỗi logic/nhầm lẫn thật, mới trong file amazon_fr.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: low  
**reason**: survives_escalation=true, dup_guess=none. Xác minh: :97-112 không có so sánh country_code. LOW vì postal-code-in-HTML (:306) bù một phần; đây là code-correctness/misleading, không phải data-corruption trực tiếp.

## Impact

- Domain: amazon-crawl-logic / fix-regression-verify
- Source: P4 (survives_escalation=true)
