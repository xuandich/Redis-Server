# BUG-35: submit-job accepts & echoes 'mode' but never propagates it (phantom contract)

**Severity**: LOW
**Status**: OPEN
**Date**: 2026-06-19

## Problem

`submit_job` đọc `mode`, log + trả trong response, nhưng KHÔNG truyền vào `queue.enqueue`. `crawl_job` không có param `mode`. Worker `process_single_request` có đọc `mode` nhưng `run.py` build request từ env `URL/RET_KEY/PROXY_TYPE` only — không set mode. → `mode` client gửi bị drop end-to-end, API response echo lại như thể đã honored.

### Root Cause

- [Dashboard/app.py:775](Dashboard/app.py#L775) — `mode = data.get('mode', 'none').strip()`, echo ở [app.py:831](Dashboard/app.py#L831).
- [Dashboard/app.py:813-821](Dashboard/app.py#L813-L821) — enqueue chỉ `url, domain, ret_key, proxy_type` (không mode).
- [main.py:70](main.py#L70) — `crawl_job(url, domain, ret_key, proxy_type='standard')` — không có mode.
- [run.py:13-25](workers/fnac/run.py#L13-L25) — request không có key mode.

Lưu ý: `mode` trong worker cũng chỉ là dự phòng (sourceCode/main.py:23 comment "dự phòng"), không branch logic → kể cả truyền xuống cũng không đổi hành vi.

## Impact

- Contract giả: response echo mode nhưng vô tác dụng
- Hiện tại mode không dùng nên impact = cosmetic

## Fix

Hoặc bỏ `mode` khỏi response (cho khớp thực tế), hoặc truyền xuyên suốt nếu sau này cần:
```python
# nếu muốn giữ contract: bỏ mode khỏi response
return jsonify({'ret_key': ret_key, 'status': 'queued', 'domain': domain, 'url': url}), 202
```

## Test

```bash
curl -X POST .../api/submit-job -d '{"url":"...","ret_key":"k","mode":"full"}'
# response echo mode:'full' nhưng worker luôn dùng 'none'
```
