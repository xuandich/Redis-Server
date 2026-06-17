#!/bin/bash
# Start Redis Server with Docker Compose
# Auto-resolve PROXY_HOST_DIR và check Chromium

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_DIR="${PROJECT_ROOT}/workers/Proxy"

# Stop old containers (preserve Redis data)
echo "🛑 Stopping old containers..."
docker compose stop > /dev/null 2>&1 && echo "   ✅ Stopped" || echo "   ⓘ No old containers"

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

# Setup Docker image cache directory
IMAGE_CACHE_DIR="$PROJECT_ROOT/Redis_Docker_Image"
mkdir -p "$IMAGE_CACHE_DIR"

# Function to load or build Docker image
load_or_build_image() {
    local IMAGE_NAME="$1"
    local SERVICE_NAME="$2"
    local CACHE_FILE="$IMAGE_CACHE_DIR/${IMAGE_NAME//[:\/]/-}.tar.gz"

    if docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
        echo "✅ $IMAGE_NAME already in system"
        return 0
    fi

    echo "📦 $IMAGE_NAME not found in system"

    if [ -f "$CACHE_FILE" ]; then
        echo "   📂 Loading from cache: $(basename $CACHE_FILE)"
        if docker load -i "$CACHE_FILE" > /dev/null 2>&1; then
            echo "   ✅ Loaded: $IMAGE_NAME"
            return 0
        else
            echo "   ❌ Failed to load, rebuilding..."
        fi
    fi

    echo "   🔨 Building new image: $IMAGE_NAME"
    if docker compose build "$SERVICE_NAME" > /dev/null 2>&1; then
        echo "   ✅ Built: $IMAGE_NAME"
        echo "   💾 Saving to cache: $(basename $CACHE_FILE)"
        docker save "$IMAGE_NAME" | gzip > "$CACHE_FILE"
        echo "   ✅ Cached: $CACHE_FILE"
        return 0
    else
        echo "   ❌ Failed to build: $IMAGE_NAME"
        return 1
    fi
}

echo "🔍 Checking Docker images..."
load_or_build_image "redis_server-orchestrator:latest" "orchestrator"
load_or_build_image "redis_server-dashboard:latest" "dashboard"

# Load worker images from workers directory
echo "🔍 Checking worker Docker images..."
WORKERS_DIR="$PROJECT_ROOT/workers"
if [ -d "$WORKERS_DIR" ]; then
    for worker_dir in "$WORKERS_DIR"/*/; do
        if [ -d "$worker_dir" ]; then
            domain=$(basename "$worker_dir")
            image_name="worker-${domain}:latest"

            if docker image inspect "$image_name" > /dev/null 2>&1; then
                echo "✅ $image_name already in system"
            else
                cache_file="$IMAGE_CACHE_DIR/worker-${domain}-latest.tar.gz"
                if [ -f "$cache_file" ]; then
                    echo "📂 Loading worker $domain from cache..."
                    if docker load -i "$cache_file" > /dev/null 2>&1; then
                        echo "✅ Loaded: $image_name"
                    else
                        echo "❌ Failed to load worker $domain"
                    fi
                else
                    echo "📦 No cache found for worker $domain"
                    echo "   (Build it separately with: docker compose build worker-$domain)"
                fi
            fi
        fi
    done
fi
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

    # Wait for services to be ready
    sleep 3

    echo "✅ All services started!"
    echo "🌐 Dashboard: http://localhost:5000"
    echo "📊 Redis: localhost:6379"
    echo ""
    echo "Press Ctrl+C to stop all services"

    # Cleanup on exit
    trap "kill $DOCKER_PID 2>/dev/null" EXIT

    # Keep script alive (blocks until Ctrl+C)
    wait $DOCKER_PID
else
    # Foreground mode (no -d flag)
    docker compose up "$@"
fi
