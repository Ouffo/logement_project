from sqlalchemy.orm import Session

from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM


def save_listing(
    session: Session,
    listing: RentalListing,
) -> RentalListingORM:
    
    db_listing = (
        session.query(RentalListingORM)
        .filter(RentalListingORM.source_id == listing.source_id)
        .one_or_none()
    )

    if db_listing is None:
        db_listing = RentalListingORM(source_id=listing.source_id)
        session.add(db_listing)

    db_listing.source = listing.source
    db_listing.url = str(listing.url)
    db_listing.title = listing.title
    db_listing.description = listing.description
    db_listing.city = listing.city
    db_listing.postal_code = listing.postal_code
    db_listing.address = listing.address
    db_listing.district_name = listing.district_name
    db_listing.latitude = listing.latitude
    db_listing.longitude = listing.longitude
    db_listing.price_eur = listing.price_eur
    db_listing.surface_m2 = listing.surface_m2
    db_listing.rooms = listing.rooms
    db_listing.bedrooms = listing.bedrooms
    db_listing.furnished = listing.furnished
    db_listing.parking = listing.parking
    db_listing.quiet = listing.quiet
    db_listing.posted_at = listing.posted_at
    db_listing.collected_at = listing.collected_at
    db_listing.relevance_score = listing.relevance_score
    
    session.commit()

    session.refresh(db_listing)

    return db_listing

def get_top_listings(
    session: Session,
    limit: int = 10
) -> list[RentalListingORM]:

    return(
        session.query(RentalListingORM)
        .order_by(RentalListingORM.relevance_score.desc())
        .limit(limit)
        .all()
    )