#!/bin/bash
#
# Start Flower monitoring dashboard for Celery.
#
# Flower provides a web UI for monitoring:
# - Active/completed/failed tasks
# - Worker status
# - Queue lengths
# - Task execution times
#
# Usage:
#   ./scripts/start_flower.sh [port]
#
# Default port: 5555
# Access at: http://localhost:5555
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

# Get port (default: 5555)
PORT="${1:-5555}"

echo "=" * 60
echo "Starting Flower Monitoring Dashboard"
echo "=" * 60
echo "Port: $PORT"
echo "Access at: http://localhost:$PORT"
echo "=" * 60
echo ""

# Start Flower
exec celery -A app.core.celery_app flower --port=$PORT
