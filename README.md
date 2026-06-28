# Distributed Redis Web Crawler

<p align="center">
  <a href="https://xuandich.github.io/Redis-Server"><img src="https://img.shields.io/badge/docs-live-DC382D?style=flat-square" alt="Docs"></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/redis-7-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/docker-required-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/playwright-latest-45ba4b?style=flat-square" alt="Playwright">
  <img src="https://img.shields.io/badge/license-MIT-gray?style=flat-square" alt="License">
</p>

<p align="center">
  <b>Self-organizing distributed web crawler — add a Dockerfile, get concurrent scraping.</b><br>
  Redis queues, Docker isolation per job, atomic slot management, Cloudflare bypass.
</p>

---

## How it works

```
Client generates ret_key (format: ret_{domain}_{uuid})
       ↓
Client → POST /api/submit-job (url + ret_key)
       → Redis Queue (RQ)
       → Orchestrator (auto-discovers workers/, routes by URL domain)
       → Docker container per job (isolated, memory-capped)
       → result:{ret_key} written to Redis
       → Client polls GET /api/job/{ret_key}
```

The orchestrator scans the `workers/` directory at startup. Any folder with a `Dockerfile` becomes a domain — no config file to update.

## Quick Start

**Requirements:** Python 3.11+, Docker, `sudo snap install chromium`

```bash
# 1. Clone and configure
git clone https://github.com/xuandich/Redis-Server.git
cd Redis-Server
cp .env.example .env          # edit as needed

# 2. Start everything
./start.sh                    # builds missing images, starts all services

# 3. Open dashboard (browse to http://localhost:5000)

# 4. Submit a job (proxy_type optional: standard or none)
RET_KEY="ret_manomano_$(uuidgen)"
curl -X POST http://localhost:5000/api/submit-job \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://www.manomano.fr/p/product-123\", \"ret_key\": \"$RET_KEY\", \"proxy_type\": \"standard\"}"

# 5. Fetch result
curl http://localhost:5000/api/job/$RET_KEY

# Stop
./stop.sh          # keep Redis data
./stop.sh -clear   # wipe Redis data
```

## How to use `ret_key`

You must generate a unique `ret_key` before submitting. The server returns it in the response and uses it to track the job:

```bash
# 1. Generate ret_key (UUID format)
RET_KEY="ret_manomano_$(uuidgen)"
# Example: ret_manomano_a1b2c3d4-5678-9abc-def0-1234567890ab

# 2. Submit job with url + ret_key
curl -X POST http://localhost:5000/api/submit-job \
  -H "Content-Type: application/json" \
  -d "{
    \"url\": \"https://www.manomano.fr/p/product-123\",
    \"ret_key\": \"$RET_KEY\",
    \"proxy_type\": \"standard\"
  }"

# Response (received in ~10ms):
# {
#   "ret_key": "ret_manomano_a1b2c3d4-5678-9abc-def0-1234567890ab",
#   "status": "queued",
#   "message": "Job enqueued successfully"
# }

# 3. Fetch result later (anytime while the result is in Redis, TTL=3600s)
curl http://localhost:5000/api/job/$RET_KEY

# Response (when job is done):
# {
#   "status": "success",
#   "html": "<!DOCTYPE html>...",
#   "headers": {...},
#   "elapsed_ms": 4821,
#   ...
# }
```

**Key points:**
- `ret_key` format: `ret_{domain}_{uuid}` (e.g., `ret_manomano_abc123...`)
- **Client generates ret_key**, server returns it in the response
- Immediately after submit, server confirms the ret_key in response (job queued, not yet running)
- Save ret_key to fetch results later
- Results stay in Redis for `RESULT_TTL` seconds (default 3600s)
- Multiple jobs can run in parallel; each identified by its unique ret_key

## Supported Domains

| Domain | Browser | Cloudflare bypass | Max concurrent | Timeout |
|--------|---------|-------------------|---------------|---------|
| `fnac` | Playwright | Yes | 5 | 120s |
| `manomano` | Playwright + Xvfb | Yes (Turnstile) | 3 | 300s |
| `orchestra` | undetected-chrome | Yes | 3 | 180s |
| `newark` | Playwright | Partial | 3 | 720s |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/submit-job` | Submit a crawl job (requires `url` + `ret_key`). |
| `GET` | `/api/job/<ret_key>` | Fetch result by return key. |
| `GET` | `/api/jobs/<state>` | Paginated jobs: `queued · running · finished · failed` |
| `GET` | `/api/stats` | Counts by state and domain, success rate. |
| `GET` | `/api/workers` | Active RQ workers and current job. |
| `POST` | `/api/clear_state/<state>` | Bulk-delete all jobs in a state. |
| `POST` | `/api/cancel/<ret_key>` | Cancel a queued job. |
| `POST` | `/api/delete/<ret_key>` | Delete job and result from Redis. |

## Result format

```json
{
  "status": "success",
  "http_code": 200,
  "html": "<!DOCTYPE html>...",
  "headers": {"content-type": "text/html", "...": "..."},
  "cookies": {"session": "abc123", "...": "..."},
  "elapsed_ms": 4821,
  "total_elapsed_seconds": 5.1,
  "domain": "manomano",
  "ret_key": "ret_manomano_f3a2b1c0-5678-9abc-def0-1234567890ab",
  "url": "https://www.manomano.fr/p/product-123",
  "proxy_type": "standard",
  "log": ["✅ CF pass after 5s", "📄 485,106 bytes"],
  "error": null,
  "timestamp": 1719562843.521
}
```

## Configuration

Copy `.env.example` to `.env`. Per-domain overrides use the `_{DOMAIN}` suffix.

```ini
REDIS_HOST=redis
REDIS_PORT=6379

RESULT_TTL=3600                  # seconds to keep results in Redis
JOB_TIMEOUT_DEFAULT=120          # container kill timeout (seconds)

# Per-domain timeouts
JOB_TIMEOUT_FNAC=120
JOB_TIMEOUT_MANOMANO=300
JOB_TIMEOUT_NEWARK=720
JOB_TIMEOUT_ORCHESTRA=180

CONTAINER_MEM_LIMIT=1g
CONTAINER_SHM_SIZE=2g            # must be >512MB for Chromium

MAX_CONCURRENT_TOTAL=10          # global cap across all domains

# Per-domain concurrency caps
MAX_CONCURRENT_FNAC=5
MAX_CONCURRENT_MANOMANO=3
MAX_CONCURRENT_NEWARK=3
MAX_CONCURRENT_ORCHESTRA=3

PROXY_HOST_DIR=/path/to/Proxy    # mounted read-only into containers
```

## Adding a new domain

1. Create worker folder with `Dockerfile`:
```
workers/
└── mynewdomain/
    ├── Dockerfile          ← triggers auto-discovery
    ├── run.py              ← reads URL, RET_KEY from env; writes result to Redis
    └── sourceCode/
        ├── main.py         ← async process_single_request(request)
        ├── extractor.py
        └── requirements.txt
```

2. Add configuration to `.env` (optional if defaults work):
```ini
JOB_TIMEOUT_MYNEWDOMAIN=120      # adjust based on complexity
MAX_CONCURRENT_MYNEWDOMAIN=3     # adjust based on load capacity
```

3. Restart services:
```bash
./stop.sh && ./start.sh   # orchestrator auto-discovers new worker
```

The orchestrator scans `workers/` and automatically creates a queue `crawler:mynewdomain` and spawns workers.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose                                         │
│                                                         │
│  ┌──────────┐    ┌─────────────┐    ┌───────────────┐   │
│  │ Dashboard│    │Orchestrator │    │     Redis     │   │
│  │ :5000    │───▶│ auto-disco  │───▶│  queue+state  │   │
│  │ Flask    │    │ slot mgmt   │    │  result store │   │
│  └──────────┘    └──────┬──────┘    └───────────────┘   │
│                         │                               │
│              ┌──────────▼──────────┐                    │
│              │  Docker API         │                    │
│              │  spawn per job      │                    │
│              └──────────┬──────────┘                    │
└─────────────────────────┼───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │worker-fnac  │ │worker-mano  │ │worker-newark│
   │ 1 job each  │ │ Playwright  │ │ Playwright  │
   │ 1g RAM cap  │ │ + Xvfb + CF │ │             │
   └─────────────┘ └─────────────┘ └─────────────┘
```

## Project structure

```
├── start.sh / stop.sh        # service management
├── docker-compose.yml
├── .env.example
├── redis_server/
│   ├── orchestrator.py       # ThreadSafeWorker, domain discovery, crash recovery
│   ├── main.py               # crawl_job, slot management (Lua), container spawn
│   └── config.py
├── Dashboard/
│   └── app.py                # Flask REST API + web UI
├── workers/
│   ├── fnac/
│   ├── manomano/
│   ├── orchestra/
│   ├── newark/
│   └── Proxy/                # proxy list (Excel)
└── Run_Test/
    ├── test_api_job.py
    └── test_api_batch.py
```

## Troubleshooting

**Chromium not found**
```bash
sudo snap install chromium
```

**Worker image missing / stale**
```bash
# Replace {DOMAIN} with: fnac, manomano, newark, or orchestra
docker build --no-cache -t worker-{DOMAIN}:latest workers/{DOMAIN}/

# Example: rebuild manomano worker
docker build --no-cache -t worker-manomano:latest workers/manomano/
```

**Redis connection refused**
```bash
# Verify redis container is running and healthy
docker ps | grep redis-server

# Test API connection
curl -s http://localhost:5000/api/stats | jq .
```

**Job stuck in `running` or orphan containers**
```bash
# Stop (keeps Redis data) and restart
./stop.sh && ./start.sh   # orchestrator kills orphan containers on restart

# To also clear all Redis data
./stop.sh -clear && ./start.sh
```
