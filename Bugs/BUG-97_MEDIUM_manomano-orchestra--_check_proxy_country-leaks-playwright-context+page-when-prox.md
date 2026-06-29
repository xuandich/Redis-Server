# BUG-97_MEDIUM_manomano/orchestra:-_check_proxy_country-leaks-playwright-context+page-when-prox

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

manomano/orchestra: _check_proxy_country leaks Playwright context+page when proxy IP-check…

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:47-60 ; workers/manomano/sourceCode/extractor.py:47-60

**Description**:
In both new Playwright workers, _check_proxy_country() creates a fresh browser context and page to probe the exit IP via ipwho.is, then closes the context ONLY on the success path:

  orchestra extractor.py:50-54
    con…

**Why Real**:
Verified the code: context.close() sits on the happy path (line 54), and the bare `except Exception` (line 59) only calls add_log — there is no finally. goto(timeout=10000) through…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: Both workers/manomano/ and workers/orchestra/ Playwright extractors call _check_proxy_country() during _start_browser() to probe exit IP via ipwho.is. The method creates a fresh context+page at lines 50-51 but closes them only on success (line 54). The except block (line 59) logs the error but never closes the dangling context/page — no finally block exists. When page.goto() or response.json() fai

## Impact

- Domain: resource-leaks
- Source: P4
