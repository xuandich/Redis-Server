# BUG-96_MEDIUM_orchestra-job_timeout=180s-likely-too-short-for-3-attempt-playwright-crawl-after

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

orchestra JOB_TIMEOUT=180s likely too short for 3-attempt Playwright crawl after the BUG-7…

## Details

**Location**: .env:JOB_TIMEOUT_ORCHESTRA=180; redis_server/main.py:182; workers/orchestra/sourceCode/extractor.py:197,248,259-261,302-306; workers/orchestra/sourceCode/main.py:36

**Description**:
ef7e652 refactored orchestra to Playwright (fetch_url default max_retries=3, called at workers/orchestra/sourceCode/main.py:36). Per-attempt worst case in _navigate_and_get_html / fetch_url: goto timeout 30000ms (extract…

**Why Real**:
Confirmed orchestra uses fetch_url with default max_retries=3 and confirmed the per-attempt Playwright timeouts sum well past 180s in the CF-challenge path (the very case the worke…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: After Playwright refactor (ef7e652), orchestra worker's per-attempt timeline in CF challenge scenario: _start_browser (~5s) + _navigate_and_get_html with goto/timeout/CF-click (~62s) + restart-browser-on-CF-block (~5s) + second _navigate_and_get_html (~62s) = ~134s per attempt worst-case. With max_retries=3, worst case is ~402s total, but JOB_TIMEOUT_ORCHESTRA=180 in .env.example (though actual .e

## Impact

- Domain: retry-lifecycle
- Source: P4
