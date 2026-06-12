from pathlib import Path
from src.ingestion.sources.leboncoin_source import LeboncoinSource


def demo_extract_listings():
    source = LeboncoinSource
    folder = Path(source.storage_path)
    listings = []
    for file_path in folder.glob("*.html"):
        html = file_path.read_text(encoding="utf-8")
        listings.extend(source.parser(html))

    print(f"Extracted {len(listings)} listings.")
    for listing in listings[:10]:
        print(f"Title: {listing.title}\nPrice: {listing.price_eur}, Surface: {listing.surface_m2}, Location: {listing.postal_code}, Rooms: {listing.rooms}, URL: {listing.url}\n, description: {listing.description}\n") 

if __name__ == "__main__":
    demo_extract_listings()
