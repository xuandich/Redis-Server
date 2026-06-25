# BUG-42: Proxy volume luôn được mount bất kể proxy_type — job 'none' bị 400 khi PROXY_HOST_DIR sai

**Severity**: MEDIUM
**Status**: OPEN
**Date**: 2026-06-22

## Problem

`_spawn_and_wait_container` mount `PROXY_HOST_DIR` vào worker container **bất kể `proxy_type`**. Khi `PROXY_HOST_DIR` không hợp lệ (relative path, thư mục không tồn tại), Docker daemon trả 400 Bad Request và từ chối tạo container — ngay cả với `proxy_type='none'` (không cần proxy). Job bị stuck ở 'running' (trước BUG-15 fix) hoặc fail với exception (sau fix).

### Root Cause

[main.py:130-132](main.py#L130-L132):
```python
if PROXY_HOST_DIR:
    volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}
```

Điều kiện chỉ check `PROXY_HOST_DIR` có tồn tại không — **không check `proxy_type`**. Kết quả:
- `proxy_type='none'` + `PROXY_HOST_DIR` hợp lệ → proxy mount vào container (lãng phí, không cần)
- `proxy_type='none'` + `PROXY_HOST_DIR` không hợp lệ → Docker daemon 400 → container không được tạo → job fail

### Scenario

```
Submit job: proxy_type='none', PROXY_HOST_DIR='./workers/Proxy' (relative)

_spawn_and_wait_container:
  volumes = {
    CHROMIUM_SNAP_DIR: {...},
    './workers/Proxy': {'bind': '/app/Proxy', 'mode': 'ro'},  ← luôn thêm
  }
  docker_client.containers.run(..., volumes=volumes)
  → 400 Bad Request: invalid bind mount source
  → container KHÔNG được tạo
  → exception propagate, job fail

Kỳ vọng: proxy_type='none' → không mount proxy → container chạy bình thường
```

## Impact

- Job `proxy_type='none'` fail vô lý khi `PROXY_HOST_DIR` không hợp lệ
- Không thể workaround bằng proxy_type='none' khi proxy config bị lỗi
- Che giấu root cause: user thấy 400 Docker error thay vì proxy config error rõ ràng

## Fix

Chỉ mount proxy khi thực sự cần:
```python
# main.py:130-132
if PROXY_HOST_DIR and proxy_type == 'standard':
    volumes[PROXY_HOST_DIR] = {'bind': '/app/Proxy', 'mode': 'ro'}
```

Kết quả: `proxy_type='none'` không mount proxy → container tạo được dù `PROXY_HOST_DIR` sai.

## Test

```bash
# PROXY_HOST_DIR sai (relative hoặc không tồn tại)
# Submit job proxy_type='none'
python test_api_job.py "https://www.newark.com/x" newark none
# ✅ sau fix: container tạo được, job chạy bình thường
# ❌ hiện tại: 400 Bad Request, job fail
```
