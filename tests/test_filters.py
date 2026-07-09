from pydantic import HttpUrl

from src.processing.filters import is_valid_listing
from src.storage.models import RentalListing


def _listing(**overrides):
    defaults = dict(
        source="TestSite",
        source_id="1",
        url=HttpUrl("http://example.com/1"),
        title="Bel appartement",
        description="Lumineux et calme",
        city="Paris",
        postal_code="75013",
        price_eur=1100,
        surface_m2=30,
    )
    defaults.update(overrides)
    return RentalListing(**defaults)


def test_is_valid_listing_accepts_valid_listing():
    assert is_valid_listing(_listing()) is True


def test_is_valid_listing_rejects_price_above_1200():
    assert is_valid_listing(_listing(price_eur=1300)) is False


def test_is_valid_listing_accepts_price_at_1200_boundary():
    assert is_valid_listing(_listing(price_eur=1200)) is True


def test_is_valid_listing_rejects_surface_below_25():
    assert is_valid_listing(_listing(surface_m2=20)) is False


def test_is_valid_listing_accepts_surface_at_25_boundary():
    assert is_valid_listing(_listing(surface_m2=25)) is True


def test_is_valid_listing_rejects_search_request_in_title():
    assert is_valid_listing(_listing(title="Je recherche un appart")) is False


def test_is_valid_listing_rejects_search_request_in_description():
    assert is_valid_listing(_listing(description="Cherche colocataire")) is False


def test_is_valid_listing_rejects_search_request_case_insensitive():
    assert is_valid_listing(_listing(title="RECHERCHE appartement")) is False
