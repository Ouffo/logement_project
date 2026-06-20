from pathlib import Path
import re
from bs4 import BeautifulSoup
from src.ingestion.sources.base import RentalListingSource
from src.processing.parsers import parse_price, parse_surface
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM
from datetime import datetime, UTC
from src.utils.logger import logger
from src.ingestion.browser_client import (
    browser_context,
    open_page,
    get_rendered_html,
    close_page,
)
from src.utils.scrapping import combine_htmls, simulate_scroll, extract_body_content


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
        image_url = None

        for tag in tags:
            if "pièce" in tag:
                rooms = int(tag.split()[0])
            elif "chambre" in tag:
                bedrooms = int(tag.split()[0])
            elif "m²" in tag:
                surface_m2 = parse_surface(tag)

        relative_url = title_el.get("href")
        source_id = relative_url.split("-")[-1]
        image_el = item.select_one("img")

        if image_el:
            image_url = image_el.get("src")

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
            image_url=image_url,
        )

        listings.append(listing)

    return listings


MONTHS_FR = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


def parse_pap_posted_at(text: str) -> datetime | None:
    match = re.search(
        r"(\d{1,2})\s+([a-zéûîôàèù]+)\s+(\d{4})",
        text.lower(),
    )

    if not match:
        return None

    day = int(match.group(1))
    month = MONTHS_FR.get(match.group(2))
    year = int(match.group(3))

    if month is None:
        return None

    return datetime(year, month, day, tzinfo=UTC)


def parse_pap_source_id(url: str) -> str:
    return url.rstrip("/").split("-")[-1]

def parse_pap_energy_class(section) -> str | None:
    text_node = section.find(
        string=lambda s: s and "Classe énergie" in s
    )

    if not text_node:
        return None

    energy_block = text_node.find_parent().find_next("ul")

    if not energy_block:
        return None

    active = energy_block.select_one("li.active")

    return active.get_text(strip=True) if active else None


def parse_pap_detail_html(html: str) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    listings = []

    for section in soup.select("section.listing-detail"):
        url = section.get("data-url")

        if not url:
            logger.warning("Skipping PAP detail without url")
            continue

        h1 = section.select_one("h1")
        h2 = section.select_one("h2")

        if not h1 or not h2:
            logger.warning(f"Skipping malformed PAP detail: {url}")
            continue

        title_text = h1.get_text(" ", strip=True)
        location = h2.get_text(" ", strip=True)
        full_text = section.get_text("\n", strip=True)

        price_el = h1.select_one("span")
        if not price_el:
            logger.warning(f"Skipping PAP detail without price: {url}")
            continue

        price_eur = parse_price(price_el.get_text(" ", strip=True))

        strong_values = [
            el.get_text(" ", strip=True)
            for el in section.select("strong")
        ]

        rooms = None
        bedrooms = None
        surface_m2 = None

        for value in strong_values:
            value_lower = value.lower()

            if "pièce" in value_lower:
                rooms = int(value.split()[0])
            elif "chambre" in value_lower:
                bedrooms = int(value.split()[0])
            elif "m²" in value_lower:
                surface_m2 = parse_surface(value)

        if surface_m2 is None:
            logger.warning(f"Skipping PAP detail without surface: {url}")
            continue

        description_el = section.select_one("div p")
        description = (
            description_el.get_text("\n", strip=True)
            if description_el
            else None
        )

        energy_class = parse_pap_energy_class(section)
        if energy_class == None:
            logger.info(f"energy class None for {url}")

        image_el = section.select_one('img[src^="https://cdn.pap.fr"]')
        image_url = image_el.get("src") if image_el else None

        postal_code_match = re.search(r"(75\d{3})", location)
        postal_code = postal_code_match.group(1) if postal_code_match else None

        posted_at = parse_pap_posted_at(full_text)

        listings.append(
            RentalListing(
                source="pap",
                source_id=parse_pap_source_id(url),
                url=url,
                title=title_text,
                description=description,
                city="Paris",
                postal_code=postal_code,
                address=None,
                district_name=location,
                price_eur=price_eur,
                surface_m2=surface_m2,
                rooms=rooms,
                bedrooms=bedrooms,
                furnished="meublée" in title_text.lower()
                or "meublé" in title_text.lower()
                or "meublé" in full_text.lower(),
                parking="parking" in full_text.lower(),
                quiet="calme" in full_text.lower(),
                posted_at=posted_at,
                image_url=image_url,
                energy_class=energy_class
            )
        )

    return listings

def merge_pap_list_and_detail(
    list_listings: list[RentalListing],
    detail_listings: list[RentalListing],
) -> list[RentalListing]:
    list_by_id = {
        listing.source_id: listing
        for listing in list_listings
    }

    merged = []

    for detail in detail_listings:
        base = list_by_id.get(detail.source_id)

        if base is None:
            merged.append(detail)
            continue

        merged.append(
            RentalListing(
                source=detail.source,
                source_id=detail.source_id,
                url=detail.url or base.url,
                title=detail.title or base.title,
                description=detail.description or base.description,
                city=detail.city or base.city,
                postal_code=detail.postal_code or base.postal_code,
                address=detail.address or base.address,
                district_name=detail.district_name or base.district_name,
                latitude=detail.latitude or base.latitude,
                longitude=detail.longitude or base.longitude,
                price_eur=detail.price_eur or base.price_eur,
                surface_m2=detail.surface_m2 or base.surface_m2,
                rooms=detail.rooms or base.rooms,
                bedrooms=detail.bedrooms or base.bedrooms,
                furnished=detail.furnished
                if detail.furnished is not None
                else base.furnished,
                parking=detail.parking
                if detail.parking is not None
                else base.parking,
                quiet=detail.quiet
                if detail.quiet is not None
                else base.quiet,
                posted_at=detail.posted_at or base.posted_at,
                collected_at=base.collected_at,
                relevance_score=base.relevance_score,
                image_url=detail.image_url or base.image_url,
            )
        )

    return merged


class PapSource(RentalListingSource):
    name = "pap"
    search_url = "https://www.pap.fr/annonce/locations-appartement-paris-75-g439-du-studio-au-2-pieces-a-partir-de-1-chambres-jusqu-a-1200-euros-a-partir-de-25-m2"
    storage_path = "data/raw/pap_htmls"
    detail_storage_path = None
    parser = staticmethod(parse_pap_detail_html)

    def fetch_html(self):
        html_pages = []

        with browser_context() as context:
            search_page = open_page(context, self.search_url)
            simulate_scroll(search_page)
            html = get_rendered_html(search_page)
            close_page(search_page)

            listings = parse_pap_html(html)
            for listing in listings:
                page = open_page(context, str(listing.url))
                page.wait_for_timeout(1000)
                raw_html = get_rendered_html(page)
                cleaned_html = extract_body_content(raw_html)
                html_pages.append((str(listing.url), cleaned_html))
                close_page(page)

        combined_html = combine_htmls(html_pages, "listing-detail")

        folder = Path(self.storage_path)
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / "pap_playwright.html"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(combined_html)

    def fetch_detail_htmls(self, _: list[RentalListingORM]):
        return []
    
    def enrich_listing(
        self, 
        _: RentalListingORM,
        __: str,):
        return None