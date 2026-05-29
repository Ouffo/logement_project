from pathlib import Path

from src.ingestion.sources.pap_source import parse_pap_html
from src.utils.logger import logger

html = Path("data/raw/pap_playwright.html").read_text(encoding="utf-8")
listings = parse_pap_html(html)

logger.info(f"Number of listings found: {len(listings)}")

for i, listing in enumerate(listings):
    logger.info(f"Listing {i+1}")
    logger.info(f"Description: {listing.description[:200]}...")
    logger.info(f"Price: {listing.price_eur} EUR")
    logger.info(f"Surface: {listing.surface_m2} m²")
    logger.info(f"Rooms: {listing.rooms}")
    logger.info(f"Bedrooms: {listing.bedrooms}")
    logger.info(f"URL: {listing.url}")
    logger.info("-" * 40 +"\n")