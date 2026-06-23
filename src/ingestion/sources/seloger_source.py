import random
import re
from datetime import UTC, datetime
from pydantic import HttpUrl
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, UTC
from src.utils.logger import logger
from src.storage.repository import RentalListingSource
from src.storage.orm_models import RentalListingORM
from src.storage.models import RentalListing
from src.storage.repository import clean_htmls
from urllib.parse import (
    urlparse, 
    parse_qs, 
    urlencode, 
    urlunparse,
    urljoin, 
    urlsplit, 
    urlunsplit
)
from src.ingestion.browser_client import (
    browser_context, 
    open_page, 
    get_rendered_html,
    close_page,
)
ENERGY_CLASSES = {"A", "B", "C", "D", "E", "F", "G"}


def clean_text(text: str | None) -> str | None:
    if not text:
        return None

    text = text.replace("\u202f", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def clean_url(url: str | None) -> str | None:
    if not url:
        return None

    url = urljoin("https://www.seloger.com", url)

    parts = urlsplit(url)
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    return clean

def parse_seloger_source_id(url: str | None, card_id: str | None = None) -> str | None:
    if url:
        match = re.search(r"/(\d+)\.htm", url)
        if match:
            return match.group(1)

    if card_id:
        return card_id.replace("classified-card-", "")

    return None


def parse_price_eur(text: str | None) -> int | None:
    if not text:
        return None

    match = re.search(r"(\d[\d\s]*)\s*€", text.replace("\u202f", " "))
    if not match:
        return None

    return int(re.sub(r"\D", "", match.group(1)))


def parse_surface_m2(text: str | None) -> float | None:
    if not text:
        return None

    match = re.search(r"(\d+(?:[,.]\d+)?)\s*m²", text)
    if not match:
        return None

    return float(match.group(1).replace(",", "."))


def parse_rooms(text: str | None) -> int | None:
    if not text:
        return None

    match = re.search(r"(\d+)\s*pi[eè]ce", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_floor(text: str | None) -> int | None:
    if not text:
        return None

    match = re.search(r"(\d+)(?:er|ème|e)\s+étage", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_available_at(text: str | None) -> datetime | None:
    if not text:
        return None

    match = re.search(r"dès le\s+(\d{1,2})/(\d{1,2})/(\d{4})", text, flags=re.IGNORECASE)
    if not match:
        return None

    day, month, year = map(int, match.groups())
    return datetime(year, month, day, tzinfo=UTC)


def parse_energy_class(card) -> str | None:
    el = card.select_one('[data-testid="card-mfe-energy-performance-class"]')
    if not el:
        return None

    value = clean_text(el.get_text(" ", strip=True))
    if value and value.upper() in ENERGY_CLASSES:
        return value.upper()

    return None


def parse_postal_code(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"\((75\d{3})\)", text)
    return match.group(1) if match else None


def parse_district_name(text: str | None) -> str | None:
    if not text:
        return None

    # Exemple : Champerret-Berthier, Paris 17ème arrondissement (75017)
    match = re.search(r"([^,]+),\s*Paris", text)
    return clean_text(match.group(1)) if match else None


def parse_title(text: str | None) -> str | None:
    if not text:
        return None

    patterns = [
        r"(Appartement à louer)",
        r"(Studio à louer)",
        r"(Maison à louer)",
        r"(Loft à louer)",
        r"(Duplex à louer)",
        r"(Chambre à louer)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def parse_seloger_card(card) -> RentalListing | None:
    card_id = card.get("id")

    link = card.select_one('[data-testid="card-mfe-covering-link-testid"]')
    if link is None:
        link = card.select_one("a[href]")

    url = clean_url(link.get("href") if link else None)
    source_id = parse_seloger_source_id(url, card_id)

    price_text = clean_text(
        card.select_one('[data-testid="cardmfe-price-testid"]').get_text(" ", strip=True)
        if card.select_one('[data-testid="cardmfe-price-testid"]')
        else None
    )

    keyfacts = clean_text(
        card.select_one('[data-testid="cardmfe-keyfacts-testid"]').get_text(" ", strip=True)
        if card.select_one('[data-testid="cardmfe-keyfacts-testid"]')
        else None
    )

    header_text = clean_text(
        card.select_one('[data-testid="cardmfe-description-box-text-test-id"]').get_text(" ", strip=True)
        if card.select_one('[data-testid="cardmfe-description-box-text-test-id"]')
        else None
    )

    description = clean_text(
        card.select_one('[data-testid="cardmfe-description-text-test-id"]').get_text(" ", strip=True)
        if card.select_one('[data-testid="cardmfe-description-text-test-id"]')
        else None
    )

    address_el = card.select_one('[data-testid="cardmfe-description-box-address"]')
    address = clean_text(address_el.get_text(" ", strip=True)) if address_el else None

    full_text = clean_text(card.get_text(" ", strip=True))

    image = card.select_one('img[src*="mms.seloger.com"][src*="w="]')
    image_url = image.get("src") if image else None

    title = parse_title(header_text or full_text)
    if title == None:
        logger.info("Skipping not appartment listing")
        return None

    return RentalListing(
        source="seloger",
        source_id=source_id,
        url=HttpUrl(url),
        title=title,
        description=description,
        city="Paris",
        postal_code=parse_postal_code(header_text or full_text),
        address=address,
        district_name=parse_district_name(address or header_text or full_text),
        price_eur= parse_price_eur(price_text or full_text),
        surface_m2=parse_surface_m2(keyfacts or full_text),
        rooms=parse_rooms(keyfacts or full_text),
        bedrooms=None,
        floor=parse_floor(keyfacts or full_text),
        furnished= "meublé" in (description or "").lower(),
        parking= "parking" in (description or full_text or "").lower(),
        quiet= "calme" in (description or full_text or "").lower(),
        energy_class= parse_energy_class(card),
        available_at= parse_available_at(keyfacts or full_text),
        posted_at=None,
        image_url=image_url,
    )


def parse_seloger_search_html(html: str) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select('[data-testid="serp-core-classified-card-testid"]')

    listings = []
    seen_ids = set()

    for card in cards:
        listing = parse_seloger_card(card)

        if listing == None:
            continue

        if listing.source_id == None:
            continue

        if listing.source_id in seen_ids:
            continue

        seen_ids.add(listing.source_id)
        listings.append(listing)

    return listings

def with_page_param(url: str, page_number: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    query["page"] = [str(page_number)]

    return urlunparse(
        parsed._replace(query=urlencode(query, doseq=True))
    )

def get_seloger_max_page(page) -> int:
    buttons = page.locator("button[aria-label^='à la page']")
    max_page = 1

    for i in range(buttons.count()):
        label = buttons.nth(i).get_attribute("aria-label") or ""

        match = re.search(r"page\s+(\d+)", label)
        if match:
            max_page = max(max_page, int(match.group(1)))

    return max_page

class SeLogerSource(RentalListingSource):
    name = "seloger"
    search_url = "https://www.seloger.com/classified-search?distributionTypes=Rent&estateTypes=Apartment&locations=AD08FR31096&priceMax=1200&spaceMin=25&m=homepage_relaunch_my_last_search_classified_search_result"
    storage_path = "data/raw/seloger_htmls"
    detail_storage_path = "data/raw/seloger_details_htmls"
    parser = staticmethod(parse_seloger_search_html)

    def __init__(self, max_listings: int | None = None):
        self.max_listings = max_listings

    def fetch_html(self):
        clean_htmls(self.storage_path)
        html_pages = []

        with browser_context() as context:
            search_page = open_page(context, self.search_url)
            search_page.wait_for_timeout(random.choice([2000, 5000]))

            max_pages = get_seloger_max_page(search_page)
            close_page(search_page)

            for page_number in range(1, max_pages + 1):
                url = self.search_url if page_number == 1 else with_page_param(
                    self.search_url,
                    page_number,
                )

                page = open_page(context, url)
                page.wait_for_timeout(random.choice([2000, 5000]))

                html_pages.append(get_rendered_html(page))
                close_page(page)


        folder = Path(self.storage_path)
        folder.mkdir(parents=True, exist_ok=True)
        for i, html in enumerate(html_pages):
            file_path = folder / f"seloger_playwright_{i+1}.html"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(html)

    def fetch_detail_htmls(self, _: list[RentalListingORM]):
        return []
    
    def enrich_listing(
        self, 
        _: RentalListingORM,
        __: str,):
        return None