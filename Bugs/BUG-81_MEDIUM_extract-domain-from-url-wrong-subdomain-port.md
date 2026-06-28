# BUG-81: _extract_domain_from_url trích sai domain khi URL có subdomain hoặc port

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-28

## Problem

Hàm `_extract_domain_from_url` ([app.py:727-741](Dashboard/app.py#L727)) trích sai domain từ URL trong các trường hợp:

1. **URL với subdomain đơn giản** (ví dụ: `www.domain` thay vì `www.domain.com`)
   - Input: `https://www.domain`
   - netloc: `www.domain` (1 dấu chấm)
   - Logic: `netloc.count('.') >= 1` → True → `split('.')[-2]` = "www"
   - Output: "www" ❌ (nên là "domain")

2. **URL với port**
   - Input: `https://www.manomano.fr:8080`
   - netloc: `www.manomano.fr:8080` (chứa `:`)
   - Code không strip port
   - split('.')[-2] so sánh với "manomano:8080" → không match
   - Output: "manomano:8080" ❌ (nên là "manomano")

3. **Subdomain phức tạp**
   - Input: `https://api.v2.manomano.fr`
   - split('.')[-2] = "manomano" ✓ OK (may mà đúng)
   - Nhưng logic này dựa vào position index, không robust

## Root Cause

Line 739 chỉ xử lý 2 trường hợp cơ bản:
```python
return netloc.split('.')[-2] if netloc.count('.') >= 1 else netloc.split('.')[0]
```

- Không strip port (`:port`)
- Không validate domain có hợp lệ
- Không whitelist supported domains
- Fallback vô hạn cho bất kỳ netloc nào

## Scenario

```
1. Client: {"url": "https://www.domain:8080", ...}
   → extract_domain = "www" ❌
   → Queue: crawler:www (không tồn tại!)
   
2. Client: {"url": "https://api.manomano.fr", ...}
   → extract_domain = "api" (if only 1 dot) ❌
   → Queue: crawler:api (không tồn tại!)
```

## Impact

- Routing domain sai → job enqueue vào queue không tồn tại
- Worker không nhận job → job stuck/timeout
- Khó chẩn đoán vì netloc logic phức tạp
- Liên quan BUG-51: domain extraction sai = routing sai

## Fix

Rewrite để robust:

```python
def _extract_domain_from_url(url: str) -> str:
    """Extract domain from URL (fnac, amazon, newark, manomano, orchestra)"""
    from urllib.parse import urlparse
    
    SUPPORTED_DOMAINS = {
        'fnac': ['fnac.com', 'fnac.fr'],
        'amazon': ['amazon.', 'amazon.co'],
        'newark': ['newark.com'],
        'manomano': ['manomano.'],
        'orchestra': ['orchestra.'],
    }
    
    try:
        # 1. Parse URL, remove port
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if ':' in netloc:
            netloc = netloc.split(':')[0]
        
        # 2. Check supported domains first
        for domain, patterns in SUPPORTED_DOMAINS.items():
            for pattern in patterns:
                if pattern in netloc:
                    return domain
        
        # 3. Extract main domain từ netloc
        # www.example.com → example
        # api.example.fr → example
        # localhost → None (không supported)
        parts = netloc.split('.')
        if len(parts) >= 2:
            return parts[-2]  # second from end
        else:
            return None  # single label like 'localhost'
    except:
        return None
```

## Test

```python
assert _extract_domain_from_url('https://www.fnac.com/product') == 'fnac'
assert _extract_domain_from_url('https://api.fnac.fr') == 'fnac'
assert _extract_domain_from_url('https://amazon.com:8080/product') == 'amazon'
assert _extract_domain_from_url('https://www.newark.com') == 'newark'
assert _extract_domain_from_url('https://www.manomano.fr') == 'manomano'
assert _extract_domain_from_url('https://api.v2.manomano.fr:9000') == 'manomano'
assert _extract_domain_from_url('https://www.domain') == 'domain'  # fallback
assert _extract_domain_from_url('https://localhost:8080') == None  # not supported
assert _extract_domain_from_url('https://internal-server') == None  # not supported
```

## Related

- BUG-51: routing by retkey instead of URL (domain extraction là source of truth)
- BUG-16: submit-job-accepts-unsupported-domain (validation nên dùng domain extraction này)
