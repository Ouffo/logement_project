from src.scoring.ranker import compute_listing_score
from src.storage.models import RentalListing

def test_compute_listing_score():
    listing = RentalListing(
        source="TestSite",
        source_id="123",
        url="http://example.com/listing/123",
        title="Test Listing",
        city="Paris",
        postal_code="75013",
        price_eur=1100,
        surface_m2=30,
        rooms=2,
        furnished=True,
        parking=True,
        quiet=True
    )

    score = compute_listing_score(listing)
    assert score == 100.0, f"Expected score of 100.0 but got {score}"

def test_compute_listing_score_partial_match():
    listing = RentalListing(
        source="TestSite",
        source_id="124",
        url="http://example.com/listing/124",
        title="Test Listing 2",
        city="Paris",
        postal_code="75020",  # Not in preferred areas
        price_eur=1300,  # Above max price
        surface_m2=20,  # Below min surface
        rooms=1,  # Below min rooms
        furnished=False,  # Does not match preference
        parking=False,  # Does not match preference
        quiet=False  # Does not match preference
    )

    score = compute_listing_score(listing)
    expected_score = 0.0  # No criteria met
    assert score == expected_score, f"Expected score of {expected_score} but got {score}"

def test_compute_listing_score_partial_preferences():
    listing = RentalListing(
        source="TestSite",
        source_id="125",
        url="http://example.com/listing/125",
        title="Test Listing 3",
        city="Paris",
        postal_code="75013",  # In preferred areas
        price_eur=1100,  # Below max price
        surface_m2=30,  # Above min surface
        rooms=2,  # Meets min rooms
        furnished=False,  # Does not match preference
        parking=True,  # Matches preference
        quiet=False  # Does not match preference
    )

    score = compute_listing_score(listing)
    expected_score = 90.0  # Meets price, surface, rooms, and parking preferences
    assert score == expected_score, f"Expected score of {expected_score} but got {score}"
