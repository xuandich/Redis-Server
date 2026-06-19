# Distributed Redis Web Crawler

Hệ thống crawl web phân tán dùng Redis, RQ, Docker và Playwright.

## 🚀 Quick Start

### 1. Cài Đặt Dependencies

**Với UV (khuyên dùng):**
```bash
uv sync
```

**Với pip (không có UV):**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Khởi Động Hệ Thống

```bash
./start.sh          # Foreground (xem log trực tiếp)
./start.sh -quiet   # Background (chạy im lặng)
```

Hệ thống sẽ tự động:
- ✅ Khởi động Redis container
- ✅ Khởi động Orchestrator (auto-discover domains)
- ✅ Khởi động Dashboard (http://localhost:5000)

### 3. Gửi Request

```bash
# Single request (qua Redis trực tiếp)
uv run python test_job.py "https://www.fnac.com/product" "fnac"

# Batch (100 URLs từ Excel, qua Redis)
uv run python test_batch.py 100 fnac

# Single request (qua HTTP API)
uv run python test_api_job.py "https://www.fnac.com/product" "fnac"

# Batch (qua HTTP API)
uv run python test_api_batch.py 100 fnac
```

### 4. Monitor Jobs

Mở trình duyệt: **http://localhost:5000**

## 📋 Yêu Cầu Hệ Thống

- **Python:** ≥3.11
- **Docker:** Latest version
- **Chromium snap:** `sudo snap install chromium`
- **Disk:** ~2GB

## 📚 Cấu Trúc Thư Mục

```
├── README.md               # File này
├── Mo_Ta.md                # Mô tả chi tiết hệ thống
├── requirements.txt        # Dependencies (pip)
├── pyproject.toml          # Config UV
├── config.py               # Cấu hình chính
├── main.py                 # crawl_job, slot management, container spawn
├── orchestrator.py         # ThreadSafeWorker, domain discovery, crash recovery
├── start.sh                # Script khởi động
├── docker-compose.yml      # Docker config
├── test_job.py             # Test trực tiếp qua Redis
├── test_batch.py           # Batch test qua Redis
├── test_api_job.py         # Test qua HTTP API
├── test_api_batch.py       # Batch test qua HTTP API
├── Dashboard/              # Flask dashboard
│   ├── app.py
│   └── Dockerfile
├── Redis_Docker_Image/     # Docker images đã build (.tar.gz)
│   ├── redis_server-orchestrator-latest.tar.gz
│   └── redis_server-dashboard-latest.tar.gz
└── workers/
    ├── fnac/
    │   ├── Dockerfile
    │   ├── run.py
    │   └── sourceCode/
    └── Proxy/
        └── buyproxies_List.xlsx
```

## 🔧 Cấu Hình (.env)

```ini
REDIS_HOST=redis
REDIS_PORT=6379
CRAWLER_NETWORK=crawler-net
PROXY_HOST_DIR=./workers/Proxy
RESULT_TTL=3600
JOB_TIMEOUT=120
MAX_CONCURRENT_TOTAL=10
MAX_CONCURRENT_FNAC=5
MAX_CONCURRENT_AMAZON=3
```

## 💡 Cách Hoạt Động

1. **Client** gửi request → enqueue vào Redis queue (`crawler:{domain}`)
2. **Orchestrator** chạy `MAX_CONCURRENT_{DOMAIN}` worker threads per domain
3. Mỗi **ThreadSafeWorker** pick 1 job, kiểm tra slot (global + domain), rồi chạy `crawl_job`
4. `crawl_job` acquire slot (atomic Lua), spawn Docker container (worker image)
5. **Worker container** fetch URL bằng Playwright, lưu `result:{ret_key}` → Redis
6. **Client** poll `result:{ret_key}` nhận kết quả

> **ThreadSafeWorker**: chạy job in-process (không fork), dùng `TimerDeathPenalty` thay SIGALRM — thread-safe, không zombie, không deadlock.
>
> **Crash recovery**: khi orchestrator restart, `_retry_stale_jobs` tự re-enqueue các job bị mất.

## 📊 API Results

```json
{
  "status": "success",
  "http_code": 200,
  "html": "...",
  "headers": {},
  "cookies": {},
  "elapsed_ms": 5000,
  "total_elapsed_seconds": 5.0,
  "error": null
}
```

## 🆘 Troubleshooting

### Chromium not found
```bash
sudo snap install chromium
```

### Docker image not found — build từ source
```bash
cd workers/fnac
docker build -t worker-fnac:latest .
```

### Docker image not found — load từ cache
```bash
docker load < Redis_Docker_Image/redis_server-orchestrator-latest.tar.gz
docker load < Redis_Docker_Image/redis_server-dashboard-latest.tar.gz
```

### Redis connection error
```bash
docker ps  # Verify redis-server running
```

## 📝 License

MIT
