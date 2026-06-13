from pathlib import Path
from src.utils.logger import logger

from src.ingestion.sources.base import RentalListingSource

def extract_all_listings(source: RentalListingSource):
    folder = Path(source.storage_path)
    logger.info(f"Folder exists: {folder.exists()}")
    logger.info(f"Folder: {folder}")

    listings = []
    for file_path in folder.glob("*.html"):
        html = file_path.read_text(encoding="utf-8")
        listings.extend(source.parser(html))

    logger.info(f"Extracted {len(listings)} listings from {folder}")

    return listings