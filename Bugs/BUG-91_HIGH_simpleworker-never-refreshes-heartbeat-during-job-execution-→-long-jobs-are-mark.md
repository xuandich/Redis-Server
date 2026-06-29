# BUG-91_HIGH_simpleworker-never-refreshes-heartbeat-during-job-execution-→-long-jobs-are-mark

**Severity**: HIGH  
**Status**: OPEN  
**Date Found**: 2026-06-29  

## Summary

SimpleWorker never refreshes heartbeat during job execution → long jobs are marked Abandon…

## Details

**Location**: redis_server/orchestrator.py:123-130 (SimpleWorker + job_monitoring_interval=5); contrast .venv/lib/python3.11/site-packages/rq/worker/worker_classes.py:99-102 (maintain_heartbeats only in monitor_work_horse) vs worker_classes.py:216-219 (SimpleWorker.execute_job has no monitor)

**Description**:
The orchestrator runs every job in-process via ThreadSafeWorker(SimpleWorker) (redis_server/orchestrator.py:43, instantiated 123-130). For RQ 2.9.1 the per-execution heartbeat is maintained ONLY by the forking Worker.mon…

**Why Real**:
Verified against installed RQ 2.9.1 source (rq.__version__=2.9.1). get_heartbeat_ttl=min(job.timeout,job_monitoring_interval)+60 with job_monitoring_interval=5 → 65s execution/work…

## Verdict (P5)

**is_real**: true  
**is_new**: true  
**severity**: high  
**reason**: SimpleWorker.execute_job() (redis_server/.venv/lib/python3.11/site-packages/rq/worker/worker_classes.py:216-220) does not maintain job heartbeats during execution, unlike the forking Worker class which calls maintain_heartbeats() every job_monitoring_interval seconds (line 102 in monitor_work_horse). This means the execution record's TTL, set to timeout+60 (e.g., 180s for default 120s timeout), is

## Impact

- Domain: worker-resilience
- Source: P4
