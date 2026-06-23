from save_listings import save_listings
from extract_listings import extract_all_listings
from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.seloger_source import SeLogerSource
from src.ingestion.sources.pap_source import PapSource
from src.storage.repository import get_listings_to_enrich
from src.storage.db import SessionLocal
from src.storage.repository import deduplicate_listings, mark_missing_listings_inactive, enrich_listings
from src.utils.logger import logger

def daily_pipeline():
    session = SessionLocal()

    sources = [
        #PapSource(),
        #LeboncoinSource(),
        #BieniciSource(),
        SeLogerSource(),
    ]

    try:
        for source in sources:
            logger.info(f"Running pipeline for source: {source.name}")
            # This will fetch html
            source.fetch_html()
            # Extract listings from html
            listings = extract_all_listings(source)
            listings = deduplicate_listings(listings)
            # saving listing in DB
            save_listings(session, listings)
            logger.info("Saved listings")

            logger.info("Inactivating passed listings")
            mark_missing_listings_inactive(
                session=session,
                source_name=source.name,
                latest_listings=listings,
            )
            session.commit()
            logger.info("Committed source listings")

            logger.info("Getting listings to enrich")
            listings_to_enrich = get_listings_to_enrich(
                session=session,
                source_name=source.name,
            )

            print(f"number of listing to enrich = {len(listings_to_enrich)}")

            enrich_listings(source, listings_to_enrich)
            session.commit()
            logger.info("Committed enrichment data")


    except Exception:
        session.rollback()
        logger.exception("Pipeline ends with error")
        raise
        
    finally:
        session.close()

if __name__ == "__main__":
    daily_pipeline()