# BUG-24: Worker success result omits 'domain' — dashboard shows domain='unknown'

**Severity**: MEDIUM
**Status**: FIXED
**Date**: 2026-06-19
**Related**: cùng root với BUG-25 (fix chung)

## Problem

Result dict của job thành công (`HtmlFetchResult.to_dict()`) **không có field `domain`**. `crawl_job` đọc result back chỉ `setdefault('timestamp')`, không backfill `domain` dù có sẵn biến. Dashboard đọc `result.get('domain', 'unknown')` → mọi job thành công hiển thị `domain='unknown'`, stats `by_domain` sai. Error paths thì CÓ domain → contract không nhất quán.

### Root Cause

1. [extractor.py:31-41](workers/fnac/sourceCode/extractor.py#L31-L41) — `to_dict()` trả `{url, html, headers, http_code, cookies, elapsed_ms, error, status}` — **không có domain**.

2. [workers/fnac/sourceCode/main.py:59-65](workers/fnac/sourceCode/main.py#L59-L65) — thêm `ret_key, total_elapsed_seconds, mode, proxy_type` — vẫn không domain.

3. [run.py:44](workers/fnac/run.py#L44) — ghi dict này verbatim vào `result:{ret_key}`.

4. [main.py:171-175](main.py#L171-L175) — `crawl_job` đọc back, `setdefault('timestamp')`, return — **không inject domain** dù `domain` là param có sẵn.

5. Dashboard đọc `result.get('domain', 'unknown')` ở [app.py:259](Dashboard/app.py#L259), [app.py:176](Dashboard/app.py#L176), [app.py:394](Dashboard/app.py#L394).

Đối chiếu: error paths (main.py:79, 89, 125, 164, 178) đều có `'domain': domain` → failed job có domain thật, success job không.

## Scenario

```
Submit fnac URL → crawl thành công
result:{ret_key} = {url, html, ..., status: success}  (không domain)
Dashboard /api/stats → by_domain = {'unknown': N}  (không phải {'fnac': N})
Dashboard /api/jobs → finished job hiển thị domain 'unknown'
```

## Impact

- Stats `by_domain` sai cho case phổ biến nhất (success)
- UI hiển thị 'unknown' cho job thành công, 'fnac' cho job lỗi → khó hiểu
- Không mất data crawl, chỉ sai grouping/observability

## Fix

Backfill trong `crawl_job` read-back + re-write result key (main.py:171-175):
```python
result = redis_client.get(f"result:{ret_key}")
if result:
    result_dict = json.loads(result)
    result_dict.setdefault('timestamp', time.time())
    result_dict.setdefault('domain', domain)   # ← BUG-24
    result_dict.setdefault('url', url)
    redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(result_dict, ensure_ascii=False, default=str))  # re-write
    return result_dict
```
Hoặc thêm `domain` vào run.py trước khi ghi.

## Test

```bash
python test_api_job.py "https://www.fnac.com/x" "fnac"
curl http://localhost:5000/api/stats
# ✅ by_domain = {'fnac': 1}
# ❌ hiện tại: {'unknown': 1}
```
