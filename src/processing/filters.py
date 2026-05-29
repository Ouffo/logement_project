from src.storage.models import RentalListing
from src.utils.logger import logger

def is_valid_listing(listing: RentalListing) -> bool:
    if listing.price_eur is None or listing.surface_m2 is None:
        logger.warning(f"{listing.title} is missing price or surface information")
        return False
    if listing.price_eur > 1200:
        logger.warning(f"{listing.title} has a price higher than 1200 EUR")
        return False 
    if listing.surface_m2 < 25:
        logger.warning(f"{listing.title} has a surface area less than 25 m2")
        return False
    return True