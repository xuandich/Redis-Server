#!/bin/bash
# Stop all services (Redis, Orchestrator, Dashboard, Workers)
# Usage: ./stop.sh          # Stop normally (keep Redis data)
#        ./stop.sh -clear   # Stop and clear all jobs from Redis (FLUSHALL)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CLEAR_JOBS=false
if [[ "$@" == *"-clear"* ]]; then
    CLEAR_JOBS=true
fi

# Load .env
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

REDIS_PORT=${REDIS_PORT:-6379}
CRAWLER_NETWORK=${CRAWLER_NETWORK:-crawler-net}

echo "🛑 Stopping services..."
echo ""

# Clear Redis if -clear flag provided
if [ "$CLEAR_JOBS" = true ]; then
    echo "🗑️  Clearing all Redis data..."
    if command -v redis-cli &> /dev/null; then
        redis-cli -p $REDIS_PORT FLUSHALL > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "  ✅ Redis data cleared (FLUSHALL)"
        else
            echo "  ⚠️  Could not clear Redis (might not be running yet)"
        fi
    else
        echo "  ⚠️  redis-cli not found, skipping Redis cleanup"
        echo "     Install: sudo apt-get install redis-tools"
    fi
    echo ""
fi

# Stop and remove all containers on the project network (workers + compose services)
ALL_IDS=$(docker ps -q --filter "network=$CRAWLER_NETWORK")
if [ -n "$ALL_IDS" ]; then
    COUNT=$(echo "$ALL_IDS" | wc -l)
    echo "🔧 Stopping $COUNT container(s) on network '$CRAWLER_NETWORK'..."
    echo "$ALL_IDS" | xargs docker stop > /dev/null 2>&1
    echo "$ALL_IDS" | xargs docker rm > /dev/null 2>&1
    echo "  ✅ All containers stopped and removed"
    echo ""
fi

# Remove compose containers (handles exited ones not caught by network filter)
docker compose down > /dev/null 2>&1

echo ""
if [ "$CLEAR_JOBS" = true ]; then
    echo "✅ All services stopped and Redis cleared!"
else
    echo "✅ All services stopped successfully"
    echo "   💡 Tip: Use './stop.sh -clear' to also clear Redis"
fi
