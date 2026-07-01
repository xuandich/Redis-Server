# BUG-106_LOW_dashboard: `_extract_domain_from_url` dùng substring match không ranh giới nhãn → host lạ/typo route nhầm tới worker thật

**Severity**: LOW  
**Status**: OPEN  
**Date Found**: 2026-07-01  

## Summary

`_extract_domain_from_url` khớp domain bằng `if pattern in netloc` (substring, không ranh giới nhãn). Vì vậy host như `notfnac.com` (chứa `fnac.`), `amazon.fr.evil.com` (chứa `amazon.fr`) hay `mymanomano.co` bị route tới worker thật tương ứng — sai định tuyến cho input lạ/gõ nhầm/giả mạo.

## Details

**Location**: Dashboard/app.py:728-745 (SUPPORTED_DOMAINS patterns + vòng `for ... if pattern in netloc: return domain`)

**Description**:
```
SUPPORTED_DOMAINS = {'fnac':['fnac.'], 'amazon_fr':['amazon.fr'], 'newark':['newark.'],
                     'manomano':['manomano.'], 'orchestra':['orchestra.']}
...
for domain, patterns in SUPPORTED_DOMAINS.items():
    for pattern in patterns:
        if pattern in netloc:          # substring, KHÔNG kiểm ranh giới nhãn/suffix
            return domain
```
`'fnac.' in 'notfnac.com'` → True → route 'fnac'. `'amazon.fr' in 'amazon.fr.malicious.com'` → True → route 'amazon_fr'. Không dùng so khớp suffix theo nhãn (vd `netloc == d or netloc.endswith('.'+d)`).

**Why Real**:
BUG-81 (đã FIXED) xử lý sai subdomain/port; đây là góc KHÁC — thiếu ranh giới nhãn trong substring match → mis-route cho host lạ. Với crawler nội bộ (operator submit URL tin cậy) rủi ro thấp, nhưng vẫn là lỗi định tuyến thật: URL gõ nhầm/không đúng domain có thể bị đẩy vào sai worker thay vì bị từ chối. LOW.

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: low  
**reason**: survives_escalation=true, dup_guess=none. Phân biệt với BUG-81 (subdomain/port) — đây là substring-no-boundary. LOW do threat model nội bộ (input tin cậy) nhưng cơ chế mis-route có thật.

## Impact

- Domain: dashboard-routing
- Source: P4 (survives_escalation=true)
