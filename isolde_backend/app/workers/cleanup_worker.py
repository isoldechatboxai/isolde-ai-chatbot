import logging

logger = logging.getLogger("IsoldeWorkers")

def system_cleanup_task():
    """
    Background worker task to purge expired temporary data and old logs.
    """
    logger.info("[CleanupWorker] Running routine database and cache cleanup...")
    # Database cleanup queries go here
    logger.info("[CleanupWorker] System cleanup completed successfully.")