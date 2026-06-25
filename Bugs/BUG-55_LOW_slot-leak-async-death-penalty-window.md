# BUG-55: Rò rỉ slot khi TimerDeathPenalty bắn vào khe hở giữa INCR và try/finally

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-23

## Problem

`crawl_job` acquire global slot và domain slot **trước khi** vào các block `try/finally` chịu trách nhiệm release chúng. Nếu RQ bắn `JobTimeoutException` bất đồng bộ (qua `ctypes.PyThreadState_SetAsyncExc`) đúng vào khe hở giữa lúc lệnh Lua INCR đã commit thành công và lúc câu lệnh `try:` (đang trang bị `finally` release) được thực thi, thì counter slot đã tăng nhưng không bao giờ giảm.

## Root Cause

Trong [main.py](redis_server/main.py#L77-L115), slot được acquire ngoài phạm vi bảo vệ của `finally`:

```python
if not _acquire_slot('global', 'total', MAX_CONCURRENT_TOTAL):  # INCR commit ở đây
    ...
try:                                            # finally release global chỉ bắt đầu ở đây
    ...
    if not _acquire_slot('domain', domain, max_domain):   # domain INCR commit ở đây
        ...
    _set_job_state(ret_key, 'running', ...)     # round-trip Redis, interruptible, CHƯA vào try bảo vệ
    try:                                        # finally release domain chỉ bắt đầu ở đây
        ...
    finally:
        _release_slot('domain', domain)
```

RQ chạy `crawl_job` bên trong `with self.death_penalty_class(timeout, ...)` (lớp được set tại [orchestrator.py](redis_server/orchestrator.py#L50)). `TimerDeathPenalty` inject exception bất đồng bộ vào bytecode bất kỳ. Nếu nó rơi vào sau khi INCR trả về True nhưng trước khi `try` bao bọc được vào (đặc biệt là trong lúc `_set_job_state` ở dòng 94 — một round-trip Redis bổ sung nằm ngay trong khe hở này), thì `_release_slot` tương ứng trong `finally` không bao giờ chạy.

Lưu ý: vì `JobTimeoutException` kế thừa từ `Exception`, nếu injection rơi vào trong `try` nội bộ thì đã bị `except Exception` bắt và cả hai `finally` đều chạy. Chỉ còn khe hở nhỏ ở dòng 94 là rò rỉ thật (xác suất thấp).

## Scenario

Một job newark với `job_timeout=720s` chạy gần hết hạn mức. Đúng lúc `_set_job_state(ret_key, 'running', ...)` đang thực hiện round-trip Redis (sau khi domain slot INCR đã commit), death penalty deadline bắn. Async exception rơi vào trước khi `try` ở dòng 96 được vào. `slots:domain:newark` đã +1 nhưng không bao giờ -1.

## Impact

Rò rỉ slot vĩnh viễn. Mỗi lần rò rỉ hạ trần concurrency thực tế của domain/global đi 1. Vì `cleanup_stale_workers` chỉ reset counter slot lúc orchestrator khởi động ([orchestrator.py](redis_server/orchestrator.py#L201-L209)), slot bị rò rỉ tồn tại suốt vòng đời tiến trình và tích lũy dần, cuối cùng kẹt cứng một domain (`slots:domain:{domain}` ghim ở max) hoặc cả hệ thống (`slots:global:total` ghim ở `MAX_CONCURRENT_TOTAL`), khiến `_can_acquire_slots` ([orchestrator.py](redis_server/orchestrator.py#L24)) luôn trả về False và mọi worker thread quay vòng vô tận ở cổng sleep/heartbeat mà không dequeue được gì.

## Fix

Acquire mỗi slot **bên trong** `try` bảo vệ nó, và release trong `finally` chỉ khi đã acquire thành công (dùng cờ boolean):

```python
global_acquired = False
domain_acquired = False
try:
    global_acquired = _acquire_slot('global', 'total', MAX_CONCURRENT_TOTAL)
    if not global_acquired:
        ...
        return
    domain_acquired = _acquire_slot('domain', domain, max_domain)
    if not domain_acquired:
        ...
        return
    _set_job_state(ret_key, 'running', ...)
    ...
finally:
    if domain_acquired:
        _release_slot('domain', domain)
    if global_acquired:
        _release_slot('global', 'total')
```

Như vậy không còn bytecode interruptible nào tách INCR khỏi việc trang bị `finally` release.

## Related

Liên quan đến nhóm bug slot-leak và job-state-not-cleared-on-basexception đã ghi nhận, nhưng đây là khe hở mới ở tầng async death penalty.
