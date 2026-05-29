from bs4 import BeautifulSoup

from src.ingestion.sources.base import RentalListingSource
from src.processing.parsers import parse_price, parse_surface
from src.storage.models import RentalListing
from src.utils.logger import logger
from src.ingestion.browser_client import (
    browser_context,
    open_page,
    get_rendered_html,
    close_page,
)
from src.utils.scrapping import simulate_scroll


class PapSource(RentalListingSource):
    name = "pap"
    search_url = "https://www.pap.fr/annonce/locations-appartement-paris-75-g439-du-studio-au-2-pieces-a-partir-de-1-chambres-jusqu-a-1200-euros-a-partir-de-25-m2"

    def fetch_listings(self) -> list[RentalListing]:        
        with browser_context() as context:
            search_page = open_page(context, self.search_url)
            simulate_scroll(search_page)
            html = get_rendered_html(search_page)
            close_page(search_page)

        with open(f"data/raw/pap_playwright.html", "w", encoding="utf-8") as file:
            file.write(html)

        return parse_pap_html(html)

def parse_pap_html(html: str) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    listings = []

    for item in soup.select(".search-list-item-alt"):
        price_el = item.select_one(".item-price")
        title_el = item.select_one(".item-title")
        location_el = item.select_one(".h1")

        if not (
            price_el
            and title_el
            and location_el
        ) or not price_el.text.strip() or not title_el.text.strip() or not location_el.text.strip():
            logger.warning("Skipping malformed listing")
            continue

        price_text = price_el.get_text(strip=True)
        location = location_el.get_text(strip=True)
        description = item.select_one(".item-description").get_text(" ", strip=True)

        tags = [
            tag.get_text(" ", strip=True)
            for tag in item.select(".item-tags li")
        ]

        rooms = None
        bedrooms = None
        surface_m2 = None

        for tag in tags:
            if "pièce" in tag:
                rooms = int(tag.split()[0])
            elif "chambre" in tag:
                bedrooms = int(tag.split()[0])
            elif "m²" in tag:
                surface_m2 = parse_surface(tag)

        relative_url = title_el.get("href")
        source_id = relative_url.split("-")[-1]

        listing = RentalListing(
            source="pap",
            source_id=source_id,
            url=f"https://www.pap.fr{relative_url}",
            title=location,
            description="\n".join(line for line in description.splitlines() if line.strip()),
            price_eur=parse_price(price_text),
            surface_m2=surface_m2,
            rooms=rooms,
            bedrooms=bedrooms,
            postal_code=None,
            district_name=location,
            furnished="meublé" in description.lower(),
            parking="parking" in description.lower(),
            quiet="calme" in description.lower(),
        )

        listings.append(listing)

    return listings