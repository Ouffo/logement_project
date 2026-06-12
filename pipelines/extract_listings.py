from pathlib import Path

from src.ingestion.sources.base import RentalListingSource

def extract_all_listings(source: RentalListingSource):
    folder = Path(source.storage_path)
    listings = []
    for file_path in folder.glob("*.html"):
        html = file_path.read_text(encoding="utf-8")
        listings.extend(source.parser(html))

    return listings