# BUG-88_HIGH_render_timeout-branch-is-dead-in-both-new-playwright-workers-—-page.wait_for_fun

**Severity**: HIGH  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

render_timeout branch is dead in both new Playwright workers — page.wait_for_function time…

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:263 (and 266,311); workers/manomano/sourceCode/extractor.py:278 (and 281,328)

**Description**:
In the refactored Playwright workers, after CF passes, both orchestra and manomano wait for the body to render >5000 chars:

orchestra extractor.py:258-268
```python
try:
    await page.wait_for_function('document.body &…

**Why Real**:
Verified empirically that playwright.async_api.TimeoutError is not a subclass of the builtin TimeoutError, so the `except TimeoutError` clause cannot catch wait_for_function's time…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: high  
**reason**: Both workers/orchestra/sourceCode/extractor.py:263 and workers/manomano/sourceCode/extractor.py:278 attempt to catch builtin TimeoutError, but playwright.async_api.Page.wait_for_function() raises playwright._impl._errors.TimeoutError, which is not a subclass of the builtin TimeoutError. When wait_for_function times out, the exception is silently caught by the generic "except Exception" clause (lin

## Impact

- Domain: false-success
- Source: P4
