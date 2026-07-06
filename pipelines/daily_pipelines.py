import os
import argparse
from datetime import datetime, UTC
from save_listings import save_listings
from extract_listings import extract_all_listings
from src.ingestion.sources.bienici_source import BieniciSource
from src.ingestion.sources.leboncoin_source import LeboncoinSource
from src.ingestion.sources.seloger_source import SeLogerSource
from src.ingestion.sources.base import RentalListingSource
from src.ingestion.sources.pap_source import PapSource
from src.storage.repository import get_listings_to_enrich, get_listings_to_score_image
from src.storage.db import SessionLocal
from src.storage.orm_models import RentalListingORM
from src.storage.repository import deduplicate_listings, mark_missing_listings_inactive, enrich_listings
from src.scoring.image_scorer import score_listing_image
from src.scoring.ranker import compute_listing_score
from src.utils.logger import logger
from src.storage.registry import (
    SOURCE_REGISTRY,
    FETCH_SOURCE_LOCK_IDS,
    EXTRACT_SAVE_SOURCE_LOCK_IDS,
    ENRICH_LOCK_IDS,
    IMAGE_SCORING_LOCK_ID,
    FINAL_SCORING_LOCK_ID,
)
from sqlalchemy import text

def _lock_id(name: str) -> int:
    import hashlib
    return int(hashlib.sha256(f"pipeline:{name}".encode()).hexdigest()[:15], 16) % (2 ** 62)

SOURCE_LOCK_IDS = {
    "pap":       _lock_id("pap"),
    "leboncoin": _lock_id("leboncoin"),
    "bienici":   _lock_id("bienici"),
    "seloger":   _lock_id("seloger"),
}

def daily_pipeline():
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
           run_source_pipeline(source)

        # Image scoring (all active listings not yet scored)
        run_image_scoring()

        # Rescore all active listings to include image scores
        run_final_scoring()

        success = True

    except Exception:
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

def fetch_source_html(source: RentalListingSource):
    session = SessionLocal()
    lock_id = FETCH_SOURCE_LOCK_IDS["fetch_"+source.name]
    acquired = False    
    success = False

    try:
        acquired = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"), 
            {"lock_id": lock_id},
        ).scalar()

        if not acquired:
            logger.warning(f"Fetch {source.name} html already running — aborting to avoid lock conflicts")
            return
        
        logger.info("=" * 50)
        logger.info(f"Fetching {source.name} html...")
        logger.info("=" * 50)

        source.fetch_html()
        logger.info(f"Fetched {source.name} html")

        success = True

    except Exception:
        session.rollback()
        logger.exception(f"Fetching {source.name} html ends with error")
        raise

    finally:
        logger.info("=" * 50)
        if success:
            logger.info(f"Fetching {source.name} html finished successfully")
        else:
            logger.info(f"Fetching {source.name} html finished with error")

        logger.info("=" * 50)
        if acquired:
            session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"), 
                {"lock_id":lock_id},
            ).scalar()
        session.close()

def extract_and_save_source_listings(source: RentalListingSource):
    session = SessionLocal()
    lock_id = EXTRACT_SAVE_SOURCE_LOCK_IDS["extract_save_"+source.name]
    success = False
    acquired = False

    try:
        acquired = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"), 
            {"lock_id": lock_id},
        ).scalar()

        if not acquired:
            logger.warning(f"Extract and save {source.name} listings already running — aborting to avoid lock conflicts")
            return 

        # Extract listings from html
        listings = extract_all_listings(source)
        listings = deduplicate_listings(listings)
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
        success = True

    except Exception:
        session.rollback()
        logger.exception(f"Extract {source.name} listings ends with error")
        raise

    finally:
        logger.info("=" * 50)
        if success:
            logger.info(f"Extract and save {source.name} listings finished successfully")
        else:
            logger.info(f"Extract and save {source.name} listings finished with error")

        logger.info("=" * 50)
        if acquired:
            session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"), 
                {"lock_id":lock_id},
            ).scalar()

        session.close()

def run_enrich_listings(source: RentalListingSource):
    session = SessionLocal()
    lock_id = ENRICH_LOCK_IDS["enrich_"+source.name]
    success = False
    acquired = False

    try:
        acquired = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"), 
            {"lock_id": lock_id},
        ).scalar()

        if not acquired:
            logger.warning(f"Enrich {source.name} listings already running — aborting to avoid lock conflicts")
            return

        logger.info("Getting listings to enrich")
        listings_to_enrich = get_listings_to_enrich(
            session=session,
            source_name=source.name,
        )

        logger.info(f"number of listing to enrich = {len(listings_to_enrich)}")

        enrich_listings(source, listings_to_enrich)
        session.commit()
        logger.info("Committed enrichment data")
        success = True

    except Exception:
        session.rollback()
        logger.exception(f"Enrich {source.name} listings ends with error")
        raise   

    finally:
        logger.info("=" * 50)
        if success:
            logger.info(f"Enrich {source.name} listings finished successfully")
        else:
            logger.info(f"Enrich {source.name} listings finished with error")

        logger.info("=" * 50)
        if acquired:
            session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"), 
                {"lock_id":lock_id},
            ).scalar()

        session.close()        


def run_source_pipeline(source: RentalListingSource):
    fetch_source_html(source)
    extract_and_save_source_listings(source)
    run_enrich_listings(source)

def run_image_scoring():
    session = SessionLocal()

    acquired = session.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": IMAGE_SCORING_LOCK_ID}).scalar()
    if not acquired:
        logger.warning("Image scoring already running — aborting to avoid lock conflicts")
        session.close()
        return

    success = False

    try:
        # Image scoring (all active listings not yet scored)
        listings_to_image_score = get_listings_to_score_image(session)
        logger.info(f"Scoring images for {len(listings_to_image_score)} listings")
        for listing in listings_to_image_score:
            score_listing_image(listing)
        session.commit()
        success = True
        logger.info("Committed image scores")

    except Exception:
        session.rollback()
        logger.exception(f"Score listings image ends with error")
        raise

    finally:
        logger.info("=" * 50)
        if success:
            logger.info(f"Score listings image finished successfully")
        else:
            logger.info(f"Score listings image finished with error")

        logger.info("=" * 50)
        session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": IMAGE_SCORING_LOCK_ID}).scalar()
        session.close()

def run_final_scoring():
    session = SessionLocal()

    acquired = session.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": FINAL_SCORING_LOCK_ID}).scalar()
    if not acquired:
        logger.warning("Final scoring already running — aborting to avoid lock conflicts")
        session.close()
        return

    success = False

    try:
        # Rescore all active listings to include image scores
        active_listings = (
            session.query(RentalListingORM)
            .filter(RentalListingORM.is_active == True)
            .all()
        )
        for listing in active_listings:
            listing.relevance_score = compute_listing_score(listing)
        session.commit()
        success = True
        logger.info("Rescored all active listings")

    except Exception:
        session.rollback()
        logger.exception(f"Pipeline ends with error")
        raise
    
    finally:
        logger.info("=" * 50)
        if success:
            logger.info(f"Final scoring finished successfully")
        else:
            logger.info(f"Final scoring ends with error")

        logger.info("=" * 50)
        session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": FINAL_SCORING_LOCK_ID}).scalar()
        session.close()

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--task",
        choices=[
            "fetch-source",
            "extract-save-source",
            "enrich-source",
            "image-scoring",
            "final-scoring",
            "all",
        ],
        default="all",
    )

    parser.add_argument(
        "--source",
        choices=list(SOURCE_REGISTRY.keys()),
    )

    args = parser.parse_args()

    source_tasks = {
        "fetch-source",
        "extract-save-source",
        "enrich-source",
    }

    if args.task in source_tasks and not args.source:
        raise ValueError("--source is required")

    source = SOURCE_REGISTRY[args.source]() if args.source else None

    if args.task == "fetch-source":
        fetch_source_html(source)

    elif args.task == "extract-save-source":
        extract_and_save_source_listings(source)

    elif args.task == "enrich-source":
        run_enrich_listings(source)

    elif args.task == "image-scoring":
        run_image_scoring()

    elif args.task == "final-scoring":
        run_final_scoring()

    elif args.task == "all":
        daily_pipeline()

if __name__ == "__main__":
    main()