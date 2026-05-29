from pathlib import Path

from src.ingestion.sources.leboncoin_source import parse_leboncoin_html


html = Path(
    "data/raw/leboncoin/details_combined.html"
).read_text(encoding="utf-8")

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