from pathlib import Path

from src.ingestion.sources.leboncoin_source import parse_leboncoin_html
from src.utils.logger import logger

logger.info("Testing parse_leboncoin_html with sample HTML")

html = Path(
    "data/raw/leboncoin.html"
).read_text(encoding="utf-8")

logger.info("parsing HTML content...")
listings = parse_leboncoin_html(html)

print(f"Parsed listings: {len(listings)}")

for listing in listings:
    print(
        listing.source_id,
        listing.title,
        listing.price_eur,
        listing.surface_m2,
        listing.rooms,
        listing.postal_code,
    )