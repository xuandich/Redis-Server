# BUG-63: Newark worker bỏ qua env PROXY_DIR, hardcode path tương đối → crawl 0 proxy âm thầm nếu đổi CWD/mount

**Severity**: LOW (latent — hiện tại resolve đúng nhờ trùng CWD)
**Status**: OPEN
**Date**: 2026-06-26

## Problem

Orchestrator truyền `PROXY_DIR=/app/Proxy` cho **mọi** worker container ([main.py:169](../redis_server/main.py#L169)) và bind-mount proxy dir tại `/app/Proxy` ([main.py:155](../redis_server/main.py#L155)). fnac honor đúng: [fnac/sourceCode/config.py:6](../workers/fnac/sourceCode/config.py#L6) đọc `PROXY_DIR` và build absolute path. **newark thì KHÔNG**: entry point Redis của nó hardcode path **tương đối theo CWD** tại [newark/sourceCode/main.py:24](../workers/newark/sourceCode/main.py#L24):
```python
proxies = load_proxies_from_excel('Proxy/buyproxies_List.xlsx')
```
và default trong [newark/sourceCode/utils.py:6](../workers/newark/sourceCode/utils.py#L6) cũng tương đối. `PROXY_DIR` không được đọc ở đâu trong `newark/sourceCode` (grep: chỉ `CHROMIUM_PATH` được đọc từ env). Hiện chỉ resolve đúng do **trùng hợp**: newark Dockerfile `WORKDIR /app`, `run.py` chạy `python run.py` (CWD=/app), mount tại `/app/Proxy` → `'Proxy/...'` → `/app/Proxy/buyproxies_List.xlsx`.

### Root Cause

- newark không tuân hợp đồng env `PROXY_DIR` mà orchestrator đã cung cấp.
- `load_proxies_from_excel()` trả `[]` **không raise** khi file thiếu ([utils.py:10-11](../workers/newark/sourceCode/utils.py#L10)) → fail âm thầm.

## Scenario

```
Đổi WORKDIR/CWD newark, hoặc orchestrator mount proxy ở path khác /app/Proxy
  → 'Proxy/buyproxies_List.xlsx' không resolve
  → load_proxies_from_excel() trả [] (không lỗi)
  → newark crawl KHÔNG proxy → dễ bị block/captcha, http_code=0 (BUG-53) → false-success
```

## Impact

- Hợp đồng env-var bị vỡ cho 1 trong 2 worker → fragile khi đổi layout
- Fail âm thầm (0 proxy) thay vì lỗi rõ ràng

## Fix

newark đọc `PROXY_DIR` như fnac:
```python
proxy_dir = os.environ.get('PROXY_DIR', '/app/Proxy')
proxies = load_proxies_from_excel(os.path.join(proxy_dir, 'buyproxies_List.xlsx'))
```
Cân nhắc cho `load_proxies_from_excel` raise/cảnh báo khi `proxy_type='standard'` mà file thiếu, thay vì trả `[]` lặng lẽ.

## Test

```bash
docker exec <newark-worker> python -c "import os; print(os.environ.get('PROXY_DIR'))"  # /app/Proxy
# Sau fix: log newark phải thể hiện đọc proxy từ PROXY_DIR, không phụ thuộc CWD
```
