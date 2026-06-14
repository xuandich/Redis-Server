#!/bin/bash
# Start RQ Dashboard for monitoring jobs
# Usage: ./dashboard.sh

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get Redis host/port from .env
if [ -f "$PROJECT_ROOT/.env" ]; then
    export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
fi

REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

echo "🚀 Starting RQ Dashboard..."
echo "📊 Redis: $REDIS_HOST:$REDIS_PORT"
echo "🌐 Open: http://localhost:9181"
echo ""

python -m rq_dashboard \
    --redis-host "$REDIS_HOST" \
    --redis-port "$REDIS_PORT" \
    --port 9181
