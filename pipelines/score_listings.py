from src.scoring.ranker import compute_listing_score
from src.storage.db import SessionLocal
from src.storage.orm_models import RentalListingORM


def rescore_all_listings():
    session = SessionLocal()

    try:
        listings = session.query(RentalListingORM).all()

        for listing in listings:
            listing.relevance_score = compute_listing_score(listing)

        session.commit()

    finally:
        session.close()


if __name__ == "__main__":
    rescore_all_listings()