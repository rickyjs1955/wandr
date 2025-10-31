"""
Application startup tasks.

Handles initialization tasks that should run when the application starts:
- Database connection verification
- Object storage bucket initialization
- Cache warming
"""
import logging

from app.services.storage_service import get_storage_service

logger = logging.getLogger(__name__)


def initialize_storage() -> None:
    """
    Initialize object storage on application startup.

    Creates the videos bucket if it doesn't exist and verifies connectivity.
    """
    try:
        logger.info("Initializing object storage...")
        storage = get_storage_service()
        storage.initialize_bucket()
        logger.info("✅ Object storage initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize object storage: {e}")
        # Don't fail the entire application - storage might be temporarily unavailable
        logger.warning("⚠️  Application starting without storage connectivity")


def run_startup_tasks() -> None:
    """
    Run all startup tasks.

    This function is called when the FastAPI application starts.
    """
    logger.info("=" * 60)
    logger.info("Running application startup tasks...")
    logger.info("=" * 60)

    # Initialize storage
    initialize_storage()

    logger.info("=" * 60)
    logger.info("✅ Startup tasks completed")
    logger.info("=" * 60)
