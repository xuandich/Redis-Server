#!/bin/bash
# Start Redis Server with Docker Compose
# Auto-resolve PROXY_HOST_DIR và check Chromium

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_DIR="${PROJECT_ROOT}/workers/Proxy"

# Load .env for REDIS_PORT
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

REDIS_PORT=${REDIS_PORT:-6379}

# Check Proxy directory
if [ ! -d "$PROXY_DIR" ]; then
    echo "❌ Proxy directory not found: $PROXY_DIR"
    exit 1
fi

# Check Chromium snap
echo "🔍 Checking Chromium snap..."
if [ ! -f "/snap/chromium/current/usr/lib/chromium-browser/chrome" ]; then
    echo "⚠️  Chromium snap not found"
    echo ""
    echo "📝 Install Chromium snap:"
    echo "   sudo snap install chromium"
    echo ""
    read -p "Install now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo snap install chromium
        if [ $? -ne 0 ]; then
            echo "❌ Failed to install Chromium snap"
            exit 1
        fi
    else
        echo "❌ Chromium snap required to run"
        exit 1
    fi
fi

echo "✅ Chromium snap found"
echo ""
echo "📂 Project: $PROJECT_ROOT"
echo "📁 Proxy dir: $PROXY_DIR"
echo ""

# Set env var
export PROXY_HOST_DIR="$PROXY_DIR"

# Start docker compose in background (if -d flag)
if [[ "$@" == *"-d"* ]]; then
    docker compose up "$@" &
    DOCKER_PID=$!
    echo "✅ Containers started (PID: $DOCKER_PID)"

    # Wait for Redis to be ready
    sleep 3

    # Start RQ Dashboard in background
    echo "📊 Starting RQ Dashboard..."
    python -m rq_dashboard \
        --redis-host localhost \
        --redis-port "$REDIS_PORT" \
        --port 9181 &
    DASHBOARD_PID=$!
    echo "✅ Dashboard started (PID: $DASHBOARD_PID)"
    echo "🌐 Open http://localhost:9181"

    # Cleanup on exit
    trap "kill $DOCKER_PID $DASHBOARD_PID 2>/dev/null" EXIT

    # Keep script alive
    wait $DOCKER_PID
else
    # Foreground mode (no -d flag)
    docker compose up "$@"
fi
