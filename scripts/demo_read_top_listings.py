if __name__ == "__main__":
    from src.storage.db import SessionLocal
    from src.storage.repository import get_top_listings
    from src.utils.logger import logger

    session = SessionLocal()

    try:
        top_listings = get_top_listings(session=session, limit=10)

        logger.info("Top Listings:")
        for listing in top_listings:
            logger.info("-" * 40)
            logger.info(f"ID: {listing.id}")
            logger.info(f"Title: {listing.title}")
            logger.info(f"Price: {listing.price_eur} EUR")
            logger.info(f"city: {listing.city}")
            logger.info(f"Postal Code: {listing.postal_code}")
            logger.info(f"Surface: {listing.surface_m2}m²")
            logger.info(f"Rooms: {listing.rooms}")
            logger.info(f"Relevance Score: {listing.relevance_score}")

    finally:
        session.close()