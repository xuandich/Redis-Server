# BUG-90_MEDIUM_manomano-cf-block-detection-is-weaker-than-orchestra's-—-missing-the-`challenge-

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

manomano CF-block detection is weaker than orchestra's — missing the `challenge-form` HTML…

## Details

**Location**: workers/manomano/sourceCode/extractor.py:245-250 (vs orchestra/sourceCode/extractor.py:230-236)

**Description**:
The two Playwright workers diverged on CF detection. orchestra `_is_cf_blocked` (extractor.py:230-236) checks four signals:
```python
'just a moment' in title_lower or 'un instant' in title_lower or 'verify you are human…

**Why Real**:
Direct side-by-side read of both `_is_cf_blocked` definitions confirms manomano omits the `'challenge-form'` substring check that orchestra has. Both are new refactor code; the inc…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: Orchestra's `_is_cf_blocked` (extractor.py:230-236) checks for `'challenge-form' in html.lower()` as the 4th detection signal for Cloudflare blocks. Manomano's identical function (extractor.py:245-250) omits this check. Both workers were refactored to use Playwright + pyvirtualdisplay in June 28 commits (manomano in 4b90369, orchestra in ef7e652). Orchestra intentionally added the `challenge-form`

## Impact

- Domain: false-success
- Source: P4
