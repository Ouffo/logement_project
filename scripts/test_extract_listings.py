from pathlib import Path
from typing import Union
from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.seloger_source import SeLogerSource
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM
AnyListing = Union[RentalListing, RentalListingORM]
from src.ingestion.sources.pap_source import PapSource

sources = {
    "pap": PapSource(),
    "leboncoin": LeboncoinSource(),
    "bienici": BieniciSource(),
    "seloger": SeLogerSource(),
}

def demo_extract_listings():
    source = sources["seloger"]
    folder = Path(source.storage_path)
    listings: AnyListing = []
    for file_path in folder.glob("*.html"):
        html = file_path.read_text(encoding="utf-8")
        listings.extend(source.parser(html))

    print(f"Extracted {len(listings)} listings.")
    for listing in listings:        
        print(f"""
              url: {listing.url}
              price: {listing.price_eur}
              postal code: {listing.postal_code}
              surface: {listing.surface_m2}
              description: {listing.description}
              energy class: {listing.energy_class}""")

if __name__ == "__main__":
    demo_extract_listings()
