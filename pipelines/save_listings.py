from src.processing.filters import is_valid_listing
from src.scoring.ranker import compute_listing_score
from src.storage.models import RentalListing
from src.storage.db import SessionLocal
from src.storage.repository import save_listing
from src.utils.logger import logger

def save_listings(listings: list[RentalListing]):
    session = SessionLocal()

    logger.info(f"Saving {len(listings)} listings to the database")
    try: 
        valid_listings = [
            listing 
            for listing in listings 
            if is_valid_listing(listing)
        ]
        for listing in valid_listings:
            listing.relevance_score = compute_listing_score(listing)
            save_listing(session, listing)
            logger.info(f"Saved listing with source_id: {listing.source_id}")

        session.commit()
    finally:
        logger.info("Closing database session")
        session.close()