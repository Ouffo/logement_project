import os
from datetime import datetime, UTC
from save_listings import save_listings
from extract_listings import extract_all_listings
from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.seloger_source import SeLogerSource
from src.ingestion.sources.pap_source import PapSource
from src.storage.repository import get_listings_to_enrich, get_listings_to_score_image
from src.storage.db import SessionLocal
from src.storage.orm_models import RentalListingORM
from src.storage.repository import deduplicate_listings, mark_missing_listings_inactive, enrich_listings
from src.scoring.image_scorer import score_listing_image
from src.scoring.ranker import compute_listing_score
from src.utils.logger import logger

def daily_pipeline():
    session = SessionLocal()

    sources = [
        PapSource(),
        LeboncoinSource(),
        BieniciSource(),
        SeLogerSource(),
    ]

    start = datetime.now(UTC)
    success = False

    try:        
        logger.info("=" * 50)
        logger.info("Pipeline started")
        logger.info(f"Environment : {'Docker' if os.path.exists('/.dockerenv') else 'Local'}")
        logger.info(f"Date        : {start:%Y-%m-%d %H:%M:%S UTC}")
        logger.info("=" * 50)
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


        # Image scoring (all active listings not yet scored)
        listings_to_image_score = get_listings_to_score_image(session)
        logger.info(f"Scoring images for {len(listings_to_image_score)} listings")
        for listing in listings_to_image_score:
            score_listing_image(listing)
        session.commit()
        logger.info("Committed image scores")

        # Rescore all active listings to include image scores
        active_listings = (
            session.query(RentalListingORM)
            .filter(RentalListingORM.is_active == True)
            .all()
        )
        for listing in active_listings:
            listing.relevance_score = compute_listing_score(listing)
        session.commit()
        logger.info("Rescored all active listings")

        success = True

    except Exception:
        session.rollback()
        logger.exception("Pipeline ends with error")
        raise

    finally:
        duration = datetime.now(UTC) - start

        logger.info("=" * 50)
        if success:
            logger.info("Pipeline finished successfully")
        else:
            logger.info("Pipeline finished with error")

        logger.info(f"Duration: {duration}")
        logger.info("=" * 50)
        session.close()

if __name__ == "__main__":
    daily_pipeline()