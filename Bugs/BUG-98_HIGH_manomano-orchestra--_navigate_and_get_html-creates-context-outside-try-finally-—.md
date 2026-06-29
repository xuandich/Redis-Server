# BUG-98_HIGH_manomano/orchestra:-_navigate_and_get_html-creates-context-outside-try/finally-—

**Severity**: HIGH  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

manomano/orchestra: _navigate_and_get_html creates context outside try/finally — context l…

## Details

**Location**: workers/orchestra/sourceCode/extractor.py:203-282 ; workers/manomano/sourceCode/extractor.py:212-298

**Description**:
In _navigate_and_get_html the context is created several statements BEFORE the try block that is responsible for closing it:

  orchestra extractor.py:
    203  context = await self._browser.new_context(...)
    211  pag…

**Why Real**:
Confirmed line layout by grep: new_context (203/212) and new_page/add_init_script (211,213 / 220,223) are above the `try:` (238/252) whose `finally` (281/297) holds the only contex…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: high  
**reason**: In workers/orchestra/sourceCode/extractor.py:203-282 and workers/manomano/sourceCode/extractor.py:212-298, the Playwright browser context is created at lines 203/212 via `context = await self._browser.new_context(...)`, and page is created at line 211/220 via `page = await context.new_page()`, followed by `await page.add_init_script()` at lines 213-220/223-235. All three operations are async and c

## Impact

- Domain: resource-leaks
- Source: P4
