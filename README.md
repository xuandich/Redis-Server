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
Client → POST /api/submit-job
       → Redis Queue (RQ)
       → Orchestrator (auto-discovers workers/)
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

# 3. Open dashboard
open http://localhost:5000

# 4. Submit a job
curl -X POST http://localhost:5000/api/submit-job \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.manomano.fr/p/product-123", "domain": "manomano"}'

# 5. Fetch result
curl http://localhost:5000/api/job/<ret_key>

# Stop
./stop.sh          # keep Redis data
./stop.sh -clear   # wipe Redis data
```

## Supported Domains

| Domain | Browser | Cloudflare bypass | Max concurrent | Timeout |
|--------|---------|-------------------|---------------|---------|
| `fnac` | Playwright | Yes | 5 | 120s |
| `manomano` | Playwright + Xvfb | Yes (Turnstile) | 3 | 300s |
| `orchestra` | undetected-chrome | Yes | 3 | 180s |
| `newark` | Playwright | Partial | 3 | 720s |
| `amazon` | — | — | 3 | 120s |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/submit-job` | Submit a crawl job. Returns `ret_key`. |
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
  "headers": {},
  "cookies": {},
  "elapsed_ms": 4821,
  "total_elapsed_seconds": 5.1,
  "domain": "manomano",
  "ret_key": "ret_manomano_f3a2b1c0-...",
  "log": ["✅ CF pass after 5s", "📄 485,106 bytes"],
  "error": null
}
```

## Configuration

Copy `.env.example` to `.env`. Per-domain overrides use the `_{DOMAIN}` suffix.

```ini
REDIS_HOST=redis
REDIS_PORT=6379

RESULT_TTL=3600                  # seconds to keep results in Redis
JOB_TIMEOUT_DEFAULT=120          # container kill timeout (seconds)
JOB_TIMEOUT_MANOMANO=300         # per-domain override
JOB_TIMEOUT_NEWARK=720

CONTAINER_MEM_LIMIT=1g
CONTAINER_SHM_SIZE=2g            # must be >512MB for Chromium

MAX_CONCURRENT_TOTAL=10          # global cap across all domains
MAX_CONCURRENT_FNAC=5            # per-domain cap
MAX_CONCURRENT_MANOMANO=3

PROXY_HOST_DIR=/path/to/Proxy    # mounted read-only into containers
```

## Adding a new domain

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

Restart — the orchestrator picks it up. Add `JOB_TIMEOUT_MYNEWDOMAIN` and `MAX_CONCURRENT_MYNEWDOMAIN` to `.env` if the defaults don't fit.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose                                          │
│                                                          │
│  ┌──────────┐    ┌─────────────┐    ┌───────────────┐   │
│  │ Dashboard│    │Orchestrator │    │     Redis     │   │
│  │ :5000    │───▶│ auto-disco  │───▶│  queue+state  │   │
│  │ Flask    │    │ slot mgmt   │    │  result store │   │
│  └──────────┘    └──────┬──────┘    └───────────────┘   │
│                         │                                │
│              ┌──────────▼──────────┐                     │
│              │  Docker API         │                     │
│              │  spawn per job      │                     │
│              └──────────┬──────────┘                     │
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
docker build --no-cache -t worker-manomano:latest workers/manomano/
```

**Redis connection refused**
```bash
docker ps   # verify redis container is healthy
```

**Job stuck in `running`**
```bash
./stop.sh && ./start.sh   # orchestrator kills orphan containers on restart
```
