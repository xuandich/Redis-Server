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
./start.sh -d
```

Hệ thống sẽ tự động:
- ✅ Khởi động Redis container
- ✅ Khởi động Orchestrator (auto-discover domains)
- ✅ Khởi động RQ Dashboard (http://localhost:9181)

### 3. Gửi Request

```bash
python test_job.py "https://www.fnac.com/product" "fnac"
```

### 4. Monitor Jobs

Mở trình duyệt: **http://localhost:9181**

## 📋 Yêu Cầu Hệ Thống

- **Python:** ≥3.11
- **Docker:** Latest version
- **Chromium snap:** `sudo snap install chromium`
- **Disk:** ~2GB

## 📚 Cấu Trúc Thư Mục

```
├── README.md               # File này
├── Mo_Ta.txt              # Mô tả chi tiết hệ thống
├── requirements.txt        # Dependencies (pip)
├── pyproject.toml         # Config UV
├── config.py              # Cấu hình chính
├── main.py                # Orchestrator helpers
├── orchestrator.py        # Orchestrator logic
├── test_job.py            # Test client
├── start.sh               # Script khởi động
├── docker-compose.yml     # Docker config
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
PROXY_HOST_DIR=./workers/Proxy
RESULT_TTL=3600
JOB_TIMEOUT=120
MAX_CONCURRENT_TOTAL=10
MAX_CONCURRENT_FNAC=5
MAX_CONCURRENT_AMAZON=3
```

## 💡 Cách Hoạt Động

1. **Client** gửi request → Redis queue
2. **Orchestrator** pick job từ queue
3. **Orchestrator** spawn Docker container (worker)
4. **Worker** fetch URL, lưu result → Redis
5. **Client** poll Redis nhận kết quả

## 📊 API Results

```json
{
  "status": "success",
  "http_code": 200,
  "html": "...",
  "headers": {...},
  "cookies": {...},
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

### Docker image not found
```bash
cd workers/fnac
docker build -t worker-fnac:latest .
```

### Redis connection error
```bash
docker ps  # Verify redis-server running
```

## 📖 Chi Tiết Hơn

Xem file **Mo_Ta.txt** để biết thêm chi tiết về:
- Architecture
- Job workflow
- Proxy rotation
- Concurrency control
- Timeout handling

## 📝 License

MIT
