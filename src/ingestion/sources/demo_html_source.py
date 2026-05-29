from src.storage.models import RentalListing
from bs4 import BeautifulSoup
from src.processing.parsers import (parse_price, parse_surface, parse_rooms)
from src.utils.logger import logger

def fetch_demo_html_source() -> RentalListing:
    # Simulate fetching data from an HTML source
    with open("data/raw/demo_listing.html", "r", encoding="utf-8") as file:
        html = file.read()

    soup = BeautifulSoup(html, "html.parser")

    listings = []

    for list_el in soup.select(".listing"):
        try:
            source_id = list_el.get("data-id")
            title = list_el.select_one(".title").get_text(strip=True)
            description = list_el.select_one(".description").get_text(strip=True)
            price = list_el.select_one(".price").get_text(strip=True)
            rooms = list_el.select_one(".rooms").get_text(strip=True)
            surface = list_el.select_one(".surface").get_text(strip=True)
            postal_code = list_el.select_one(".postal-code").get_text(strip=True)

            listing = RentalListing(
                source="demo_html_source",
                source_id=source_id,
                url="https://example.com/html_listing",
                title=title,
                description=description,
                price_eur=parse_price(price),
                surface_m2=parse_surface(surface),
                rooms=parse_rooms(rooms),
                postal_code=postal_code,
                furnished="meublé" in description.lower(),
                parking="parking" in description.lower(),
                quiet="calme" in description.lower()
            )

            listings.append(listing)
        except Exception as e:
            logger.error(f"Error parsing listing: {e}")
            continue
    return listings