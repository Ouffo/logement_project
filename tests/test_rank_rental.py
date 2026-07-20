from types import SimpleNamespace

import pytest
from pydantic import HttpUrl

from src.scoring.ranker import (
    compute_image_score,
    compute_listing_score,
    compute_location_score,
    compute_preferences_score,
    compute_price_score,
    compute_room_score,
    compute_surface_score,
    compute_suspicion_penalty,
)
from src.storage.models import RentalListing


def _listing(**overrides):
    defaults = dict(
        price_eur=1100,
        surface_m2=30,
        rooms=2,
        postal_code="75013",
        furnished=True,
        parking=True,
        quiet=True,
        clear_view=False,
        image_url="http://example.com/image.jpg",
        image_score=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_compute_listing_score():
    listing = RentalListing(
        source="TestSite",
        source_id="123",
        url=HttpUrl("http://example.com/listing/123"),
        title="Test Listing",
        city="Paris",
        postal_code="75013",
        price_eur=1100,
        surface_m2=30,
        rooms=2,
        furnished=True,
        parking=True,
        quiet=True,
    )

    score = compute_listing_score(listing)
    expected_score = 54.83  # No image_url set, so suspicion penalty applies
    assert score == expected_score, f"Expected score of {expected_score} but got {score}"


def test_compute_listing_score_partial_match():
    listing = RentalListing(
        source="TestSite",
        source_id="124",
        url=HttpUrl("http://example.com/listing/124"),
        title="Test Listing 2",
        city="Paris",
        postal_code="75020",  # Not in preferred areas
        price_eur=1300,  # Above max price
        surface_m2=20,  # Below min surface
        rooms=1,  # Below min rooms
        furnished=False,  # Does not match preference
        parking=False,  # Does not match preference
        quiet=False,  # Does not match preference
    )

    score = compute_listing_score(listing)
    expected_score = 0.0  # No criteria met
    assert score == expected_score, f"Expected score of {expected_score} but got {score}"


def test_compute_listing_score_partial_preferences():
    listing = RentalListing(
        source="TestSite",
        source_id="125",
        url=HttpUrl("http://example.com/listing/125"),
        title="Test Listing 3",
        city="Paris",
        postal_code="75013",  # In preferred areas
        price_eur=1100,  # Below max price
        surface_m2=30,  # Above min surface
        rooms=2,  # Meets min rooms
        furnished=False,  # Does not match preference
        parking=True,  # Matches preference
        quiet=False,  # Does not match preference
    )

    score = compute_listing_score(listing)
    expected_score = 39.83  # Meets price, surface, rooms, and parking preferences
    assert score == expected_score, f"Expected score of {expected_score} but got {score}"


def test_compute_price_score_missing_price():
    assert compute_price_score(_listing(price_eur=0)) == 0


def test_compute_price_score_at_or_above_max():
    assert compute_price_score(_listing(price_eur=1200)) == 0


def test_compute_price_score_below_max():
    assert compute_price_score(_listing(price_eur=1100)) == pytest.approx(15.8333, abs=1e-3)


def test_compute_surface_score_missing_surface():
    assert compute_surface_score(_listing(surface_m2=0)) == 0


def test_compute_surface_score_below_min():
    assert compute_surface_score(_listing(surface_m2=20)) == 0


def test_compute_surface_score_above_min():
    assert compute_surface_score(_listing(surface_m2=30)) == 19.0


def test_compute_room_score_meets_min():
    assert compute_room_score(_listing(rooms=2)) == 10


def test_compute_room_score_below_min():
    assert compute_room_score(_listing(rooms=1)) == 5


def test_compute_room_score_missing():
    assert compute_room_score(_listing(rooms=None)) == 5


def test_compute_location_score_preferred_area():
    assert compute_location_score(_listing(postal_code="75013")) == 20


def test_compute_location_score_other_area():
    assert compute_location_score(_listing(postal_code="75020")) == 5


def test_compute_preferences_score_all_matched():
    assert compute_preferences_score(_listing(furnished=True, parking=True, quiet=True)) == 20


def test_compute_preferences_score_none_matched():
    assert compute_preferences_score(_listing(furnished=False, parking=False, quiet=False)) == 0


def test_compute_preferences_score_clear_view_bonus():
    assert (
        compute_preferences_score(
            _listing(furnished=False, parking=False, quiet=False, clear_view=True)
        )
        == 5
    )


def test_compute_image_score_missing():
    assert compute_image_score(_listing(image_score=None)) == 0


def test_compute_image_score_clamped_upper():
    assert compute_image_score(_listing(image_score=25)) == 15


def test_compute_image_score_clamped_lower():
    assert compute_image_score(_listing(image_score=-5)) == 0


def test_compute_image_score_normal():
    assert compute_image_score(_listing(image_score=8)) == 8


def test_compute_suspicion_penalty_missing_price_or_surface():
    assert compute_suspicion_penalty(_listing(price_eur=0)) == 0
    assert compute_suspicion_penalty(_listing(surface_m2=0)) == 0


def test_compute_suspicion_penalty_low_price_and_large_surface():
    # price<900 and surface>=30 (+35) combined with price_per_m2<30 (+30), clamped to 60
    listing = _listing(price_eur=850, surface_m2=30)
    assert compute_suspicion_penalty(listing) == 60


def test_compute_suspicion_penalty_price_per_m2_tiers():
    assert compute_suspicion_penalty(_listing(price_eur=1200, surface_m2=30)) == 0  # 40 eur/m2
    assert compute_suspicion_penalty(_listing(price_eur=1170, surface_m2=30)) == 10  # <40 eur/m2
    assert compute_suspicion_penalty(_listing(price_eur=1020, surface_m2=30)) == 20  # <35 eur/m2
    assert compute_suspicion_penalty(_listing(price_eur=900, surface_m2=35)) == 30  # <30 eur/m2


def test_compute_suspicion_penalty_large_cheap_surface():
    # price<=1200 and surface>=45 (+20) combined with price_per_m2<30 (+30)
    listing = _listing(price_eur=1200, surface_m2=45)
    assert compute_suspicion_penalty(listing) == 50


def test_compute_suspicion_penalty_no_image_url():
    listing = _listing(price_eur=1200, surface_m2=30, image_url=None)
    assert compute_suspicion_penalty(listing) == 20
