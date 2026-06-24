# Distributed Redis Web Crawler

Hệ thống crawl web phân tán dùng Redis, RQ, Docker và Playwright.

## 🚀 Quick Start

### 1. Cài Đặt Dependencies

```bash
uv sync
```

### 2. Khởi Động Hệ Thống

```bash
./start.sh          # Foreground (xem log trực tiếp)
./start.sh -quiet   # Background (chạy im lặng)
```

Hệ thống sẽ tự động:
- ✅ Khởi động Redis container
- ✅ Khởi động Orchestrator (auto-discover domains)
- ✅ Build worker images nếu chưa có
- ✅ Khởi động Dashboard (http://localhost:5000)

### 3. Gửi Request

```bash
cd Run_Test

# Single job qua HTTP API
python test_api_job.py newark
python test_api_job.py "https://www.newark.com/dp/100A00001" newark standard

# Batch qua HTTP API
python test_api_batch.py 10 newark
python test_api_batch.py 50 fnac none
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
├── start.sh                # Script khởi động
├── stop.sh                 # Script dừng
├── docker-compose.yml      # Docker config
├── .env                    # Cấu hình môi trường
├── redis_server/           # Orchestrator service
│   ├── config.py           # Cấu hình chính
│   ├── main.py             # crawl_job, slot management, container spawn
│   ├── orchestrator.py     # ThreadSafeWorker, domain discovery, crash recovery
│   ├── requirements.txt
│   └── Dockerfile
├── Run_Test/               # Test scripts
│   ├── test_api_job.py     # Test single job qua HTTP API
│   ├── test_api_batch.py   # Batch test qua HTTP API
│   └── README.md           # Hướng dẫn test
├── TEST_FILE/              # Excel files chứa URLs
├── Dashboard/              # Flask dashboard
│   ├── app.py
│   └── Dockerfile
└── workers/
    ├── Proxy/
    │   └── buyproxies_List.xlsx
    ├── fnac/
    │   ├── Dockerfile
    │   ├── run.py
    │   └── sourceCode/
    └── newark/
        ├── Dockerfile
        ├── run.py
        └── sourceCode/
```

## 🔧 Cấu Hình (.env)

```ini
REDIS_HOST=redis
REDIS_PORT=6379
CRAWLER_NETWORK=crawler-net
RESULT_TTL=3600
JOB_TIMEOUT_DEFAULT=120       # Timeout mặc định cho tất cả domain
JOB_TIMEOUT_NEWARK=720        # Override riêng cho newark
CONTAINER_MEM_LIMIT=1g
CONTAINER_SHM_SIZE=2g
MAX_CONCURRENT_TOTAL=10
MAX_CONCURRENT_FNAC=5
MAX_CONCURRENT_NEWARK=3
```

## 💡 Cách Hoạt Động

1. **Client** gửi `POST /api/submit-job` với `ret_key=ret_{domain}_{uuid}`
2. **API** parse domain từ `ret_key`, enqueue vào `crawler:{domain}`
3. **Orchestrator** chạy `MAX_CONCURRENT_{DOMAIN}` worker threads per domain
4. Mỗi **ThreadSafeWorker** check slot → dequeue → `crawl_job`
5. `crawl_job` acquire slot (atomic Lua), spawn Docker container
6. **Worker container** fetch URL bằng Playwright, lưu `result:{ret_key}` → Redis
7. **Client** poll `GET /api/job/{ret_key}` nhận kết quả

## 📊 Result Format

```json
{
  "status": "success",
  "http_code": 200,
  "html": "...",
  "headers": {},
  "cookies": {},
  "elapsed_ms": 5000,
  "total_elapsed_seconds": 5.0,
  "log": ["..."],
  "error": null
}
```

## ➕ Thêm Domain Mới

1. Tạo `workers/{domain}/` với `Dockerfile`, `run.py`, `sourceCode/`
2. Thêm `process_single_request()` vào `sourceCode/main.py`
3. Thêm `JOB_TIMEOUT_{DOMAIN}` và `MAX_CONCURRENT_{DOMAIN}` vào `.env`
4. Restart → orchestrator tự detect và tạo worker threads

## 🆘 Troubleshooting

### Chromium not found
```bash
sudo snap install chromium
```

### Worker image not found
```bash
# Rebuild thủ công
docker build -t worker-newark:latest workers/newark/
# Hoặc restart start.sh — tự build nếu chưa có image
```

### Redis connection error
```bash
docker ps  # Verify redis container running
```
