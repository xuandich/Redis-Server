# BUG-25: Worker success result omits 'timestamp' — defeats BUG-08 sort for success case

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-19
**Related**: cùng root với BUG-24 (fix chung)

## Problem

Result dict success không có `timestamp`. `crawl_job` `setdefault('timestamp')` chỉ sửa giá trị **return cho RQ** (lưu riêng dưới `rq:job:*`), **không re-write `result:{ret_key}`** — key gốc mà dashboard scan. Dashboard sort theo `timestamp`, mọi job success có `timestamp=0` → sort xuống đáy/thứ tự tùy ý → **vô hiệu hóa fix BUG-08 cho case phổ biến nhất**.

### Root Cause

1. [extractor.py:31-41](workers/fnac/sourceCode/extractor.py#L31-L41) — `to_dict()` không có `timestamp`.

2. [run.py:44](workers/fnac/run.py#L44) — ghi dict (không timestamp) vào `result:{ret_key}`.

3. [main.py:171-175](main.py#L171-L175):
```python
result_dict = json.loads(result)
result_dict.setdefault('timestamp', time.time())  # ← chỉ sửa return value
return result_dict                                 # ← KHÔNG setex lại result:{ret_key}
```
`setdefault` chỉ mutate dict in-memory trả cho RQ, không ghi lại key Redis.

4. Dashboard sort [app.py:359-360](Dashboard/app.py#L359-L360): `sort(key=lambda x: x.get('timestamp', 0), reverse=True)` → success jobs `timestamp=0`.

Đối chiếu: error paths (main.py:163-168, 177-182) đều có `'timestamp'` + setex → failed job sort đúng, success job thì không.

## Scenario

```
Chạy nhiều crawl thành công
result:{ret_key} không có timestamp → dashboard đọc = 0
GET /api/jobs: finished jobs tất cả timestamp 0, không sort newest-first
(failed jobs sort đúng vì crawl_job ghi timestamp cho chúng)
```

## Impact

- Sort dashboard sai cho success (case phổ biến nhất) → fix BUG-08 vô tác dụng
- Chỉ ảnh hưởng UX/ordering, không mất data

## Fix

Cùng fix với BUG-24 — re-write `result:{ret_key}` sau khi backfill:
```python
result_dict.setdefault('timestamp', time.time())
result_dict.setdefault('domain', domain)
redis_client.setex(f"result:{ret_key}", RESULT_TTL, json.dumps(result_dict, ensure_ascii=False, default=str))
return result_dict
```
Hoặc thêm `'timestamp': time.time()` trong run.py trước khi ghi.

## Test

```bash
for i in 1 2 3; do python test_api_job.py "https://www.fnac.com/$i" "fnac"; sleep 2; done
curl http://localhost:5000/api/jobs | python3 -c "import sys,json; d=json.load(sys.stdin); print([j['timestamp'] for j in d['finished']])"
# ✅ timestamps khác 0, sort giảm dần
# ❌ hiện tại: tất cả 0
```
