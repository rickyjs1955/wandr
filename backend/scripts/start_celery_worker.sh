#!/bin/bash
#
# Start Celery worker for video processing tasks.
#
# Usage:
#   ./scripts/start_celery_worker.sh [queue_name] [concurrency]
#
# Examples:
#   ./scripts/start_celery_worker.sh                    # All queues, auto concurrency
#   ./scripts/start_celery_worker.sh video_processing 2  # Video queue, 2 workers
#   ./scripts/start_celery_worker.sh cv_analysis 4       # CV queue, 4 workers
#

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BACKEND_DIR"

# Load environment variables
if [ -f .env ]; then
    echo "Loading environment from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Get queue name (default: all queues)
QUEUE="${1:-video_processing,cv_analysis,maintenance}"

# Get concurrency (default: number of CPU cores)
CONCURRENCY="${2:-}"

# Build celery command
CELERY_CMD="celery -A app.core.celery_app worker"

if [ -n "$CONCURRENCY" ]; then
    CELERY_CMD="$CELERY_CMD --concurrency=$CONCURRENCY"
fi

CELERY_CMD="$CELERY_CMD --queues=$QUEUE --loglevel=info"

echo "=" 60
echo "Starting Celery Worker"
echo "=" * 60
echo "Queue(s): $QUEUE"
echo "Concurrency: ${CONCURRENCY:-auto}"
echo "Log Level: info"
echo "=" * 60
echo ""

# Start worker
exec $CELERY_CMD
