# BUG-82_HIGH_the-render-completeness-guard-is-dead-code-due-to-wrong-exception-class.-wait_fo

**Severity**: HIGH  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

The render-completeness guard is dead code due to wrong exception class. wait_for_function…

## Details

**Location**: workers/manomano/sourceCode/extractor.py:278-283

**Description**:
The render-completeness guard is dead code due to wrong exception class. wait_for_function (line 274) waits for document.body.innerHTML.length > 5000 and on timeout raises playwright.async_api.TimeoutError, whose MRO is …

**Why Real**:
A page that never finished rendering product content (JS stalled, soft-block, slow proxy) is NOT classified as render_timeout and does NOT trigger the proxy-retry at line 328-330. …

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: high  
**reason**: The render-timeout exception handler at workers/manomano/sourceCode/extractor.py:278-283 and workers/orchestra/sourceCode/extractor.py:263-268 is dead code. It attempts to catch Python's built-in TimeoutError, but Playwright raises playwright._impl._errors.TimeoutError, which is NOT a subclass of the built-in. When Playwright's wait_for_function times out after 20 seconds, the exception is caught 

## Impact

- Domain: manomano
- Source: P6
