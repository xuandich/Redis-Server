# BUG-83_MEDIUM_response_headers-is-populated-only-from-responses-where-'manomano'-in-response.u

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

response_headers is populated only from responses where 'manomano' in response.url AND res…

## Details

**Location**: workers/manomano/sourceCode/extractor.py:239-241, 295

**Description**:
response_headers is populated only from responses where 'manomano' in response.url AND response.status == 200 (line 240). The document response itself (from goto) is not explicitly recorded, and if no 200 manomano respon…

**Why Real**:
A 'success' result can carry empty headers, weakening any header-based downstream checks and making the success signal less trustworthy. Not a hard failure but contributes to 'http…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: The response_headers dictionary in workers/manomano/sourceCode/extractor.py:237-241 is populated exclusively through the on('response') event handler with a filter requiring BOTH 'manomano' in response.url AND response.status == 200. The main document response from page.goto() at line 181 is not captured (await page.goto(...) discards the returned Response object). Consequently: (1) If the main do

## Impact

- Domain: manomano
- Source: P6
