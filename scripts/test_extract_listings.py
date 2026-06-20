from pathlib import Path
from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.pap_source import PapSource

sources = {
    "pap": PapSource(),
    "leboncoin": LeboncoinSource(),
    "bienici": BieniciSource()
}

def demo_extract_listings():
    source = sources["pap"]
    folder = Path(source.storage_path)
    listings = []
    for file_path in folder.glob("*.html"):
        html = file_path.read_text(encoding="utf-8")
        listings.extend(source.parser(html))

    print(f"Extracted {len(listings)} listings.")
    for listing in listings:        
        print(f"url: {listing.url} \n energy class: {listing.energy_class}")

if __name__ == "__main__":
    demo_extract_listings()
