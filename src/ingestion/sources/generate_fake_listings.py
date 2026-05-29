from src.storage.models import RentalListing
from random import randint, choice

fake_source_list = ["fake_source_logement", "fake_source_airbnb", "fake_source_paris_rental"]
fake_postal_codes_paris = ["75001", "75002", "75003", "75004", "75005", 
    "75006", "75007", "75008", "75009", "75010", "75011", "75012","75013",
    "75014","75015","75016","75017","75018","75019","75020"]

def generate_fake_listings(num_listings: int) -> list[RentalListing]:
    fake_listings = []
    for i in range(num_listings):
        listing = RentalListing(
            source=choice(fake_source_list),
            source_id=f"fake_id_{i}",
            url=f"https://fakeurl.com/listing/{i}",
            title=f"Fake Listing {i}",
            description=f"This is a description for fake listing {i}.",
            city="Paris",
            postal_code=choice(fake_postal_codes_paris),
            price_eur=randint(900,1500),
            surface_m2=randint(20, 80),
            rooms=randint(1, 3),
            furnished=choice([True, False]),
            parking=choice([True, False]),
            quiet=choice([True, False])
        )
        fake_listings.append(listing)
    return fake_listings