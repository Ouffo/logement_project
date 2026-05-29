from src.storage.db import init_db
from src.utils.logger import logger

if __name__ == "__main__":
    init_db()
    logger.info("Database initialized")