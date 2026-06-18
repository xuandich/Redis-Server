#!/bin/bash
# Stop all services (Redis, Orchestrator, Dashboard)
# Usage: ./stop.sh          # Stop normally (keep Redis data)
#        ./stop.sh -clear   # Stop and clear all jobs from Redis (FLUSHALL)

CLEAR_JOBS=false
if [[ "$@" == *"-clear"* ]]; then
    CLEAR_JOBS=true
fi

echo "🛑 Stopping services..."
echo ""

# Clear Redis if -clear flag provided
if [ "$CLEAR_JOBS" = true ]; then
    echo "🗑️  Clearing all Redis data..."

    # Load .env to get Redis port
    if [ -f ".env" ]; then
        export $(grep -v '^#' .env | xargs)
    fi

    REDIS_PORT=${REDIS_PORT:-6379}

    # Try to clear Redis using redis-cli
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

# Stop Docker containers gracefully
if docker compose stop; then
    echo "  ✅ Redis stopped"
    echo "  ✅ Orchestrator stopped"
    echo "  ✅ Dashboard stopped"
    echo "  ✅ Networks cleaned up"
else
    echo "  ⓘ Docker services not running"
fi

echo ""
if [ "$CLEAR_JOBS" = true ]; then
    echo "✅ All services stopped and Redis cleared!"
else
    echo "✅ All services stopped successfully"
    echo "   💡 Tip: Use './stop.sh -clear' to also clear Redis"
fi
