from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.pap_source import PapSource
from src.processing.filters import is_valid_listing
from src.storage.db import SessionLocal
from src.storage.repository import save_listing 
from src.scoring.ranker import compute_listing_score
from src.utils.logger import logger

def daily_pipeline():
    session = SessionLocal()

    sources = [
        PapSource(),
        LeboncoinSource(max_listings=10),  # Limit to 10 listings
    ]

    try:
        for source in sources:
            logger.info(f"Running pipeline for source: {source.name}")
            listings = source.fetch_listings()

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
        session.close()

if __name__ == "__main__":
    daily_pipeline()