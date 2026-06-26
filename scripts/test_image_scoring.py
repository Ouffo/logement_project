from src.storage.db import SessionLocal
from src.storage.orm_models import RentalListingORM
from src.scoring.image_scorer import score_listing_image


session = SessionLocal()

listings = (
    session.query(RentalListingORM)
    .filter(RentalListingORM.source == "seloger")
    .filter(RentalListingORM.source_id == "271645809")
    .all()
)

for listing in listings:
    print(f"url = {listing.url}")
    score_listing_image(listing)
    print(f"image_score = {listing.image_score}/15")