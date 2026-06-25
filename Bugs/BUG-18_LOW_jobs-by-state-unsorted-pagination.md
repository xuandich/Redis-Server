# BUG-18: get_jobs_by_state doesn't sort before pagination

**Severity**: LOW  
**Status**: OPEN  
**Date**: 2026-06-19

## Problem

`/api/jobs/<state>` endpoint ([Dashboard/app.py:71-200](Dashboard/app.py#L71-L200)) không sort job list trước khi phân trang. SCAN không đảm bảo thứ tự, nên:
- Page 1 có jobs A, B, C
- Page 2 refresh → jobs thay đổi (D, E, F)
- User có thể thấy job trùng giữa 2 trang, hoặc sót job

Trong khi `/api/jobs` ([line 359-360](Dashboard/app.py#L359-L360)) **đã sort** trước khi return:
```python
for status in ['queued', 'running', 'finished', 'failed']:
    jobs_data[status].sort(key=lambda x: x.get('timestamp', 0), reverse=True)
```

### Root Cause

[Dashboard/app.py:189-199](Dashboard/app.py#L189-L199) — phân trang trực tiếp từ all_jobs mà chưa sort:
```python
all_jobs = []  # Accumulate từ SCAN
# ... SCAN loop, append to all_jobs (order random)

total = len(all_jobs)
start = (page - 1) * per_page
end = start + per_page

return jsonify({
    'jobs': all_jobs[start:end],  # ← Slice unsorted list
    ...
})
```

SCAN iterate result theo Redis internal hash order, không guaranteed stable.

### Scenario

```
User browse page 1 at 10:00:01
  GET /api/jobs/finished?page=1
  Redis SCAN returns: [job-A, job-B, job-C, job-D, job-E]
  Page 1: [A, B, C, D, job-E]
  
User browse page 2 at 10:00:02
  GET /api/jobs/finished?page=2
  Redis SCAN returns: [job-C, job-D, job-E, job-F, job-G]  ← Order changed!
  Page 2: [F, G]
  
Result: job-C, D, E appear on page 1, partially on page 2
```

### Impact

- Minor UX issue: pagination unstable, job có thể trùng/sót
- Chỉ xảy ra khi SCAN order thay đổi (hashmap rehash → hiếm)
- Single-domain/small dataset không bị chú ý
- Dashboard trên lớn (1000s jobs) → rõ rệt

### Fix

Sort before pagination:
```python
# After collecting all_jobs
all_jobs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

# Then paginate
total = len(all_jobs)
start = (page - 1) * per_page
end = start + per_page
return jsonify({
    'jobs': all_jobs[start:end],
    ...
})
```

## Test

```bash
# Submit 50 jobs quickly
for i in {1..50}; do
  python test_api_job.py "https://www.fnac.com/$i" "fnac" &
done

# Paginate
curl http://localhost:5000/api/jobs/queued?page=1
curl http://localhost:5000/api/jobs/queued?page=2
curl http://localhost:5000/api/jobs/queued?page=3

# Compare ret_keys across pages
# ✅ Should not overlap / have gaps (after fix)
# ❌ Currently may have duplicate/missing jobs
```

**Note**: Bug hiếm vì SCAN order stable trong hầu hết case, rehash cần điều kiện nhất định.
