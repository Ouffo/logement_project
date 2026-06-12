from src.processing.filters import is_valid_listing
from src.storage.models import RentalListing
from src.storage.db import SessionLocal
from src.storage.repository import save_listing
from src.utils.logger import logger

def save_listings(listings: list[RentalListing]):
    session = SessionLocal()

    try: 
        valid_listings = [
            listing 
            for listing in listings 
            if is_valid_listing(listing)
        ]
        for listing in valid_listings:
            save_listing(session, listing)
            logger.info(f"Saved listing with source_id: {listing.source_id}")

        session.commit()

    finally:
        session.close()