from src.storage.models import RentalListing

def test_listing_model():
    listing = RentalListing(
        source="demo",
        source_id="123",
        url="https://example.com/appartement-123",
        title="Appartement meublé calme avec parking",
        price_eur=1100,
        surface_m2=28,
        rooms=2,
        postal_code="75014",
        furnished=True,
        parking=True,
        quiet=True,
    )

    assert listing.city == "Paris"
    assert listing.price_eur == 1100
    assert listing.surface_m2 == 28