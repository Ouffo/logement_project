from src.config.search_criteria import SEARCH_CRITERIA

from src.storage.models import RentalListing


def compute_listing_score(listing: RentalListing) -> float:
    score = 0.0

    # Prix
    if listing.price_eur <= SEARCH_CRITERIA["max_price"]:
        score += 35 + (SEARCH_CRITERIA["max_price"] - listing.price_eur) * 0.1

    # Surface
    if listing.surface_m2 >= SEARCH_CRITERIA["min_surface_m2"]:
        score += 15 + (SEARCH_CRITERIA["min_surface_m2"] - listing.surface_m2) * 0.5

    # Nombre de pièces
    if listing.rooms and listing.rooms >= SEARCH_CRITERIA["min_rooms"]:
        score += 10

    # Zone préférée
    if listing.postal_code in SEARCH_CRITERIA["preferred_areas"]:
        score += 25

    prefs = SEARCH_CRITERIA["preferences"]

    # Meublé
    if prefs["furnished"] and listing.furnished:
        score += 5

    # Parking
    if prefs["parking"] and listing.parking:
        score += 5

    # Calme
    if prefs["quiet"] and listing.quiet:
        score += 5

    return round(score, 2)