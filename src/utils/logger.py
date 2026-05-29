from loguru import logger

logger.add(
    "logs/rental_pipeline.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
)

__all__ = ["logger"]