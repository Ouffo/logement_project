from pathlib import Path
from src.utils.logger import logger

from src.ingestion.sources.base import RentalListingSource

def extract_all_listings(source: RentalListingSource):
    folder = Path(source.storage_path)
    logger.info(f"Folder exists: {folder.exists()}")
    logger.info(f"Folder: {folder}")

    listings = []
    for file_path in folder.glob("*.html"):
        logger.info(f"Processing file: {file_path}")
        html = file_path.read_text(encoding="utf-8")
        logger.info(f"HTML size: {len(html)}")
        logger.info(f"Contains article: {'<article' in html}")
        logger.info(f"Contains search-page: {'search-page' in html}")
        logger.info(f"Contains search-list-item-alt: {'search-list-item-alt' in html}")
        logger.info(f"Contains captcha: {'captcha' in html.lower()}")
        logger.info(f"Contains robot: {'robot' in html.lower()}")
        logger.info(f"Contains forbidden: {'forbidden' in html.lower()}")
        logger.info(f"HTML preview: {html[:500]}")
        listings.extend(source.parser(html))

    logger.info(f"Extracted {len(listings)} listings from {folder}")

    return listings