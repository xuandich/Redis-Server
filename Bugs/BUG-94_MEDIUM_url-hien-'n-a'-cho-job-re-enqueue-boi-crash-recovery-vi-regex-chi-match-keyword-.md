# BUG-94_MEDIUM_url-hien-'n/a'-cho-job-re-enqueue-boi-crash-recovery-vi-regex-chi-match-keyword-

**Severity**: MEDIUM  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

URL hien 'N/A' cho job re-enqueue boi crash-recovery vi regex chi match keyword-form url='…

## Details

**Location**: Dashboard/app.py:144, 340 (vs redis_server/orchestrator.py:225)

**Description**:
Dashboard parse URL tu RQ job description bang regex re.search(r"url='([^']+)'", description) tai app.py:144 va app.py:340. Job submit qua /api/submit-job enqueue bang KEYWORD args (app.py:825-833) -> description = "main…

**Why Real**:
Da xac minh format description that bang rq.utils.get_call_string: positional cho ra chuoi khong chua url='...' nen regex tra None -> 'N/A'. Cung co che goc voi BUG-29 (URL 'N/A' t…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: medium  
**reason**: **Root Cause**: Dashboard/app.py:144 and 340 parse the URL from RQ job description using regex `re.search(r"url='([^']+)'", description)`. This regex assumes keyword-argument form (`url='...'`), which is generated when jobs are enqueued via `/api/submit-job` using keyword args (app.py:842-850). However, when crash-recovery re-enqueues lost jobs via orchestrator.py:225, it uses positional arguments

## Impact

- Domain: dashboard-integrity
- Source: P4
