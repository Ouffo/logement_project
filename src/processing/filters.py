from src.config.search_criteria import get_search_criteria
from src.storage.models import RentalListing
from src.utils.logger import logger


def is_valid_listing(listing: RentalListing) -> bool:
    if listing.price_eur is None or listing.surface_m2 is None:
        logger.warning(f"{listing.title} is missing price or surface information")
        return False

    criteria = get_search_criteria(getattr(listing, "is_rental", True))

    if listing.price_eur > criteria["max_price"]:
        logger.warning(f"{listing.title} has a price higher than {criteria['max_price']} EUR")
        return False
    if listing.surface_m2 < criteria["min_surface_m2"]:
        logger.warning(
            f"{listing.title} has a surface area less than {criteria['min_surface_m2']} m2"
        )
        return False
    text = f"{listing.title or ''} {listing.description or ''}".lower()
    if "recherche" in text or "cherche" in text:
        logger.warning(f"{listing.title} is a search request, not an offer")
        return False
    return True
