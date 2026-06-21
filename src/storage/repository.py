from pathlib import Path
from sqlalchemy.orm import Session
from src.storage.models import RentalListing
from src.ingestion.sources.base import RentalListingSource
from src.storage.orm_models import RentalListingORM
from datetime import UTC, datetime


def save_listing(
    session: Session,
    listing: RentalListing,
) -> RentalListingORM:
    
    now = datetime.now(UTC)
    
    db_listing = (
        session.query(RentalListingORM)
        .filter(
            RentalListingORM.source == listing.source,
            RentalListingORM.source_id == listing.source_id
        )
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
    db_listing.image_url = listing.image_url
    db_listing.posted_at = listing.posted_at
    db_listing.collected_at = listing.collected_at
    db_listing.relevance_score = listing.relevance_score
    db_listing.energy_class = listing.energy_class
    db_listing.construction_year = listing.construction_year
    db_listing.details_fetched_at = listing.details_fetched_at
    db_listing.is_active = True
    db_listing.last_seen_at = now
    
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

def mark_missing_listings_inactive(session, source_name, latest_listings):
    latest_ids = {listing.source_id for listing in latest_listings}

    db_listings = (
        session.query(RentalListingORM)
        .filter(RentalListingORM.source == source_name)
        .all()
    )

    for db_listing in db_listings:
        if db_listing.source_id not in latest_ids:
            db_listing.is_active = False

def deduplicate_listings(listings):
    seen = set()
    deduped = []

    for listing in listings:
        key = (listing.source, listing.source_id)

        if key in seen:
            continue

        seen.add(key)
        deduped.append(listing)

    return deduped

def enrich_listings(
    source: RentalListingSource, 
    listings: list[RentalListingORM], 
) -> None:
    
    detail_htmls = source.fetch_detail_htmls(listings)

    if source.detail_storage_path is not None:
        folder = Path(source.detail_storage_path)
        folder.mkdir(parents=True, exist_ok=True)

        for listing, html in detail_htmls:
            file_path = folder / f"{listing.source_id}.html"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(html)
            source.enrich_listing(listing, html)
        

def get_listings_to_enrich(session, source_name: str) -> list[RentalListingORM]:
    return (
        session.query(RentalListingORM)
        .filter(RentalListingORM.source == source_name)
        .filter(RentalListingORM.is_active == True)
        .filter(RentalListingORM.details_fetched_at == None)
        .all()
    )
