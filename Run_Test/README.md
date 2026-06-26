# Redis Crawler Test Suite

Test scripts for verifying worker crawlers via the HTTP API.

## 📋 Test Files

| File | Purpose | Usage |
|---|---|---|
| `test_api_job.py` | Submit 1 job via API, poll result | `python test_api_job.py [url] [proxy_type]` |
| `test_api_batch.py` | Submit N batch jobs via API from Excel | `python test_api_batch.py [num] [domain] [proxy_type]` |

> Both files communicate via HTTP API (`localhost:5000`) — no direct Redis connection needed.

**proxy_type:**
- `standard` — use proxies from Excel file (default)
- `none` — direct connection, no proxy

---

## 🚀 Quick Start

### Single Job
```bash
# Random URL from TEST_FILE/fnac_urls.xlsx (default)
python test_api_job.py

# Random URL by domain
python test_api_job.py newark
python test_api_job.py newark none

# Direct URL
python test_api_job.py "https://www.newark.com/dp/100A00001" newark standard
python test_api_job.py "https://www.fnac.com/..." fnac none
```

### Batch
```bash
# 10 fnac jobs (default)
python test_api_batch.py 10

# 10 newark jobs
python test_api_batch.py 10 newark

# 50 newark jobs, no proxy
python test_api_batch.py 50 newark none
```

---

## 📁 Test Data

Create the folder and Excel file before running batch tests:

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

Configure in `.env`:

```env
JOB_TIMEOUT_DEFAULT=120    # default timeout for all domains
JOB_TIMEOUT_NEWARK=720     # per-domain override for newark
RESULT_TTL=3600
```

---

## 🔍 Monitoring

```bash
# Orchestrator logs
docker logs -f redis_server-orchestrator-1

# Check result in Redis
redis-cli GET result:<ret_key>

# Check current slots
redis-cli GET slots:global:total
redis-cli GET slots:domain:newark
```

---

## 🐛 Troubleshooting

**"Connection refused"** — API is not running:
```bash
bash start.sh
```

**"Timeout after 180s"** — job is slow or stuck:
```bash
# View worker container logs
docker logs worker-newark-xxx

# Increase timeout in .env
JOB_TIMEOUT_NEWARK=720
```

**"Domain not discovered"** — missing Dockerfile:
```bash
ls workers/<domain>/Dockerfile
```
