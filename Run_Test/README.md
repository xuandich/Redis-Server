# Redis Crawler Test Suite

Test scripts để kiểm tra worker crawlers qua HTTP API.

## 📋 Test Files

| File | Mục đích | Cách dùng |
|---|---|---|
| `test_api_job.py` | Submit 1 job via API, poll result | `python test_api_job.py [url] [proxy_type]` |
| `test_api_batch.py` | Batch N jobs via API từ Excel | `python test_api_batch.py [num] [domain] [proxy_type]` |

> Cả 2 file giao tiếp qua HTTP API (`localhost:5000`) — không cần kết nối Redis trực tiếp.

**proxy_type:**
- `standard` — dùng proxy từ file Excel (default)
- `none` — kết nối trực tiếp, không qua proxy

---

## 🚀 Quick Start

### Single Job
```bash
# Random URL từ TEST_FILE/fnac_urls.xlsx (default)
python test_api_job.py

# Random URL theo domain
python test_api_job.py newark
python test_api_job.py newark none

# URL trực tiếp
python test_api_job.py "https://www.newark.com/dp/100A00001" newark standard
python test_api_job.py "https://www.fnac.com/..." fnac none
```

### Batch
```bash
# 10 jobs fnac (default)
python test_api_batch.py 10

# 10 jobs newark
python test_api_batch.py 10 newark

# 50 jobs newark, không proxy
python test_api_batch.py 50 newark none
```

---

## 📁 Test Data

Tạo folder và file Excel trước khi chạy batch:

```
TEST_FILE/
└── fnac_urls.xlsx    (URLs in column A)
```

```bash
mkdir -p TEST_FILE
python -c "
import pandas as pd
urls = ['https://www.fnac.com/url1', 'https://www.fnac.com/url2']
pd.DataFrame(urls).to_excel('TEST_FILE/fnac_urls.xlsx', index=False, header=False)
"
```

---

## ✅ Expected Result Format

```json
{
  "url": "https://www.fnac.com/...",
  "ret_key": "uuid-here",
  "status": "success",
  "http_code": 200,
  "html": "...",
  "headers": {},
  "cookies": {},
  "elapsed_ms": 5000,
  "total_elapsed_seconds": 5.0,
  "proxy_type": "standard",
  "error": null,
  "log": ["..."]
}
```

---

## ⚠️ Timeout Configuration

Cấu hình trong `.env`:

```env
JOB_TIMEOUT_DEFAULT=120    # default timeout cho tất cả domain
JOB_TIMEOUT_NEWARK=720     # override riêng cho newark
RESULT_TTL=3600
```

---

## 🔍 Monitoring

```bash
# Logs orchestrator
docker logs -f redis_server-orchestrator-1

# Kiểm tra result trong Redis
redis-cli GET result:<ret_key>

# Kiểm tra slot hiện tại
redis-cli GET slots:global:total
redis-cli GET slots:domain:newark
```

---

## 🐛 Troubleshooting

**"Connection refused"** — API chưa chạy:
```bash
bash start.sh
```

**"Timeout after 180s"** — job chậm hoặc bị stuck:
```bash
# Xem log container worker
docker logs worker-newark-xxx

# Tăng timeout trong .env
JOB_TIMEOUT_NEWARK=720
```

**"Domain not discovered"** — thiếu Dockerfile:
```bash
ls workers/<domain>/Dockerfile
```
