from typing import Union

from src.config.search_criteria import SEARCH_CRITERIA
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM

AnyListing = Union[RentalListing, RentalListingORM]


def clamp(value: float, min_value: float = 0, max_value: float = 100) -> float:
    return max(min_value, min(value, max_value))


def compute_price_score(listing: AnyListing) -> float:
    if not listing.price_eur:
        return 0

    max_price = SEARCH_CRITERIA["max_price"]

    if listing.price_eur >= max_price:
        return 0

    ratio = (max_price - listing.price_eur) / max_price

    return 15 + clamp(ratio * 10, 0, 10)


def compute_surface_score(listing: AnyListing) -> float:
    if not listing.surface_m2:
        return 0

    min_surface = SEARCH_CRITERIA["min_surface_m2"]

    if listing.surface_m2 < min_surface:
        return 0

    extra_surface = listing.surface_m2 - min_surface

    return 15 + clamp(extra_surface * 0.8, 0, 10)


def compute_room_score(listing: AnyListing) -> float:
    if listing.rooms and listing.rooms >= SEARCH_CRITERIA["min_rooms"]:
        return 10

    return 5


def compute_location_score(listing: AnyListing) -> float:
    if listing.postal_code in SEARCH_CRITERIA["preferred_areas"]:
        return 20

    return 5


def compute_preferences_score(listing: AnyListing) -> float:
    prefs = SEARCH_CRITERIA["preferences"]
    score = 0

    if prefs["furnished"] and listing.furnished:
        score += 5

    if prefs["parking"] and listing.parking:
        score += 5

    if prefs["quiet"] and listing.quiet:
        score += 10

    return score


def compute_image_score(listing) -> float:
    score = getattr(listing, "image_score", None)
    if score is None:
        return 0
    return clamp(score, 0, 15)


def compute_suspicion_penalty(listing: AnyListing) -> float:
    if not listing.price_eur or not listing.surface_m2:
        return 0

    price_per_m2 = listing.price_eur / listing.surface_m2
    penalty = 0

    if listing.price_eur < 900 and listing.surface_m2 >= 30:
        penalty += 35

    if price_per_m2 < 30:
        penalty += 30
    elif price_per_m2 < 35:
        penalty += 20
    elif price_per_m2 < 40:
        penalty += 10

    if listing.price_eur <= 1200 and listing.surface_m2 >= 45:
        penalty += 20

    if listing.image_url is None:
        penalty += 20

    return clamp(penalty, 0, 60)


def compute_listing_score(listing: AnyListing) -> float:
    score = 0

    score += compute_price_score(listing)
    score += compute_surface_score(listing)
    score += compute_room_score(listing)
    score += compute_location_score(listing)
    score += compute_preferences_score(listing)
    score += compute_image_score(listing)

    score -= compute_suspicion_penalty(listing)

    return round(clamp(score, 0, 100), 2)