from save_listings import save_listings
from extract_listings import extract_all_listings
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.pap_source import PapSource
from src.storage.db import SessionLocal
from src.utils.logger import logger

def daily_pipeline():
    session = SessionLocal()

    sources = [
        PapSource(),
        LeboncoinSource(),
    ]

    try:
        for source in sources:
            logger.info(f"Running pipeline for source: {source.name}")
            # This will fetch html
            source.fetch_html()
            # Extract listings from html
            listings = extract_all_listings(source)
            # saving listing in DB
            save_listings(session, listings)

        session.commit()

    except Exception:
        session.rollback()
        raise
        
    finally:
        session.close()

if __name__ == "__main__":
    daily_pipeline()