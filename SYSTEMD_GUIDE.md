# Redis Crawler Stack — Systemd Guide

Service name: `redis-crawler`

---

## Basic Commands

### Check status
```bash
systemctl status redis-crawler
```

### Follow logs in real time
```bash
journalctl -u redis-crawler -f
```

### View last 100 log lines
```bash
journalctl -u redis-crawler -n 100
```

---

## Start / Stop / Restart

### Start service
```bash
sudo systemctl start redis-crawler
```

### Stop service (keep Redis data)
```bash
sudo systemctl stop redis-crawler
```

### Stop and clear all Redis jobs
```bash
# Run stop.sh directly with the -clear flag
sudo ./stop.sh -clear
```
> **Note:** `systemctl stop` calls `stop.sh` without `-clear`. Use the command above if you need to flush Redis data.

### Restart service
```bash
sudo systemctl restart redis-crawler
```

---

## Auto-start on Boot

The service is already enabled — it starts automatically on server reboot.

### Disable auto-start
```bash
sudo systemctl disable redis-crawler
```

### Re-enable auto-start
```bash
sudo systemctl enable redis-crawler
```

---

## Updating Code

```bash
sudo systemctl stop redis-crawler
git pull
sudo systemctl start redis-crawler
```

---

## Dashboard & Redis

| Component | Address |
|---|---|
| Dashboard | http://localhost:5000 |
| Redis | localhost:6379 |

---

## Manual Start (without systemd)

### Foreground — logs printed directly to terminal
```bash
./start.sh
```

### Background — runs silently, frees the terminal
```bash
./start.sh -quiet
```

### Manual stop
```bash
./stop.sh           # Keep Redis data
./stop.sh -clear    # Stop + flush all jobs
```

---

## Troubleshooting

### Service fails to start
```bash
journalctl -u redis-crawler -n 50
```
Check that Docker is running:
```bash
systemctl status docker
```



### Full reset (flush data and rebuild everything)
```bash
sudo systemctl stop redis-crawler
./stop.sh -clear
docker compose down --volumes
sudo systemctl start redis-crawler
```
