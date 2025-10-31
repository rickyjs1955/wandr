#!/bin/bash
#
# Start Celery Beat scheduler for periodic tasks.
#
# Beat scheduler runs periodic tasks like:
# - cleanup_old_jobs (daily at 2 AM)
# - check_stuck_jobs (every 15 minutes)
#
# Usage:
#   ./scripts/start_celery_beat.sh
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

echo "=" * 60
echo "Starting Celery Beat Scheduler"
echo "=" * 60
echo "Periodic tasks configured:"
echo "  - cleanup_old_jobs: Daily at 2 AM"
echo "  - check_stuck_jobs: Every 15 minutes"
echo "=" * 60
echo ""

# Start beat scheduler
exec celery -A app.core.celery_app beat --loglevel=info
