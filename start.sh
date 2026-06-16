#!/bin/bash
# Start Redis Server with Docker Compose
# Auto-resolve PROXY_HOST_DIR và check Chromium

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_DIR="${PROJECT_ROOT}/workers/Proxy"

# Auto-cleanup old containers before starting
echo "🛑 Cleaning up old containers..."
docker compose down > /dev/null 2>&1 && echo "   ✅ Cleaned up" || echo "   ⓘ No old containers"

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

# Auto-load orchestrator image from tar.gz if missing
echo "🔍 Checking Docker images..."
ORCHESTRATOR_IMAGE="redis_server-orchestrator:latest"
ORCHESTRATOR_BACKUP="$PROJECT_ROOT/orchestrator-latest.tar.gz"

if ! docker image inspect "$ORCHESTRATOR_IMAGE" > /dev/null 2>&1; then
    echo "📦 Orchestrator image not found: $ORCHESTRATOR_IMAGE"

    if [ -f "$ORCHESTRATOR_BACKUP" ]; then
        echo "   Loading from: orchestrator-latest.tar.gz..."
        if docker load -i "$ORCHESTRATOR_BACKUP" > /dev/null 2>&1; then
            echo "   ✅ Loaded: $ORCHESTRATOR_IMAGE"
        else
            echo "   ❌ Failed to load, rebuilding..."
            docker compose build orchestrator > /dev/null 2>&1
            echo "   ✅ Built: $ORCHESTRATOR_IMAGE"
        fi
    else
        echo "   Building new image..."
        docker compose build orchestrator > /dev/null 2>&1
        echo "   ✅ Built: $ORCHESTRATOR_IMAGE"
        echo "   💾 Saving backup to orchestrator-latest.tar.gz..."
        docker save "$ORCHESTRATOR_IMAGE" | gzip > "$ORCHESTRATOR_BACKUP"
    fi
else
    echo "✅ Orchestrator image found: $ORCHESTRATOR_IMAGE"
fi

# Auto-load worker images from tar.gz if missing
echo "🔍 Checking worker Docker images..."
WORKERS_DIR="$PROJECT_ROOT/workers"
for tar_file in "$WORKERS_DIR"/*/*.tar.gz; do
    if [ -f "$tar_file" ]; then
        filename=$(basename "$tar_file")
        # Extract domain name from filename (e.g., worker-fnac-latest.tar.gz → fnac)
        domain=$(echo "$filename" | sed 's/worker-//g' | sed 's/-latest.tar.gz//g')
        image_name="worker-${domain}:latest"

        if ! docker image inspect "$image_name" > /dev/null 2>&1; then
            echo "📦 Image not found: $image_name"
            echo "   Loading from: $filename..."
            if docker load -i "$tar_file" > /dev/null 2>&1; then
                echo "   ✅ Loaded: $image_name"
            else
                echo "   ❌ Failed to load: $image_name"
            fi
        else
            echo "✅ Image found: $image_name"
        fi
    fi
done
echo ""

echo "📂 Project: $PROJECT_ROOT"
echo "📁 Proxy dir: $PROXY_DIR"
echo ""

# Set env var
export PROXY_HOST_DIR="$PROXY_DIR"

# Start docker compose in background (if -d flag)
if [[ "$@" == *"-d"* ]]; then
    # Background docker compose (don't pass -d to it - we background manually)
    docker compose up &
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
    echo ""
    echo "Press Ctrl+C to stop all services"

    # Cleanup on exit
    trap "kill $DOCKER_PID $DASHBOARD_PID 2>/dev/null" EXIT

    # Keep script alive (blocks until Ctrl+C)
    wait $DOCKER_PID
else
    # Foreground mode (no -d flag)
    docker compose up "$@"
fi
