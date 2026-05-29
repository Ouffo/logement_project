if __name__ == "__main__":
    from src.storage.db import SessionLocal
    from src.storage.repository import save_listing
    from src.storage.models import RentalListing
    from src.scoring.ranker import compute_listing_score as compute_relevance_score
    from src.utils.logger import logger

    # Create a sample listing
    demo_listing = RentalListing(
        source="example_source",
        source_id="example_id2",
        url="https://example.com/listing",
        title="Cozy Apartment in Downtown",
        description="A cozy 2-bedroom apartment located in the heart of the city.",
        price_eur=1200,
        surface_m2=35.0,
        rooms=2,
        bedrooms=1,
        postal_code="75014",
        furnished=True,
        parking=True,
        quiet=True
    )

    demo_listing.relevance_score = compute_relevance_score(demo_listing)

    session = SessionLocal()

    try:
        saved_listing =save_listing(
            session = session,
            listing = demo_listing
            )
        
        logger.info("listing saved")
        logger.info(f"saved DB id: {saved_listing.id}")
        logger.info(f"relevance score: {saved_listing.relevance_score}")

    finally:
        session.close()
