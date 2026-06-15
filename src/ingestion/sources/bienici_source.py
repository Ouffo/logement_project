import random
import re
from bs4 import BeautifulSoup
from pathlib import Path
from src.ingestion.browser_client import browser_context, close_page, get_rendered_html, open_page
from src.ingestion.sources.base import RentalListingSource
from src.storage.models import RentalListing
from src.utils.scrapping import get_next_page_url
from src.processing.parsers import parse_price, parse_surface
from src.utils.logger import logger

def parse_bienici_search_html(html: str) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    listings = []
    seen_ids = set()

    for article in soup.select("article[data-id]"):
        source_id = article.get("data-id")

        if not source_id or source_id in seen_ids:
            continue

        seen_ids.add(source_id)

        link_el = article.select_one("a.detailedSheetLink[href]")
        if not link_el:
            logger.info(f"Skipping Bienici listing without url: {source_id}")
            continue

        href = link_el.get("href")
        url = (
            f"https://www.bienici.com{href}"
            if href.startswith("/")
            else href
        )

        title_el = article.select_one(".real-estate-main-info__title")
        address_el = article.select_one(".real-estate-main-info__address")
        price_el = article.select_one(".ad-price__the-price")
        description_el = article.select_one(".ad-overview-description")
        image_el = article.select_one("img[src*='file.bienici.com']")

        title = title_el.get_text(" ", strip=True) if title_el else None
        address = address_el.get_text(" ", strip=True) if address_el else None
        price_text = price_el.get_text(" ", strip=True) if price_el else None
        description = (
            description_el.get_text("\n", strip=True)
            if description_el
            else None
        )
        image_url = image_el.get("src") if image_el else None

        if not title or not price_text:
            logger.info(f"Skipping malformed Bienici listing: {source_id}")
            continue

        surface_m2 = parse_bienici_surface(title)
        rooms = parse_bienici_rooms(title)

        if surface_m2 is None:
            logger.info(f"Skipping Bienici listing without surface: {source_id}")
            continue

        postal_code = parse_bienici_postal_code(address)
        city = "Paris" if postal_code and postal_code.startswith("75") else None

        full_text = f"{title}\n{address or ''}\n{description or ''}"

        listing = RentalListing(
            source="bienici",
            source_id=source_id,
            url=url,
            title=title,
            description=description,
            city=city,
            postal_code=postal_code,
            address=None,
            district_name=address,
            latitude=None,
            longitude=None,
            price_eur=parse_price(price_text),
            surface_m2=surface_m2,
            rooms=rooms,
            bedrooms=None,
            furnished=(
                "meublé" in full_text.lower()
                or "meublée" in full_text.lower()
            ),
            parking="parking" in full_text.lower(),
            quiet=(
                "calme" in full_text.lower()
                or "silencieux" in full_text.lower()
            ),
            posted_at=None,
            relevance_score=None,
            image_url=image_url,
        )

        listings.append(listing)

    return listings


def parse_bienici_surface(text: str) -> float | None:
    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*m[²2]",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return parse_surface(match.group(0))


def parse_bienici_rooms(text: str) -> int | None:
    match = re.search(
        r"(\d+)\s*pi[eè]ce[s]?",
        text,
        flags=re.IGNORECASE,
    )

    return int(match.group(1)) if match else None


def parse_bienici_postal_code(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"\b(75\d{3})\b", text)
    return match.group(1) if match else None


class BieniciSource(RentalListingSource):
    name = "bienici"
    search_url = "https://www.bienici.com/recherche/location/paris-75000/appartement/1-piece-et-plus?prix-max=1200&surface-min=25"
    storage_path = "data/raw/bienici_htmls"
    parser = staticmethod(parse_bienici_search_html)

    def __init__(self, max_listings: int | None = None):
        self.max_listings = max_listings

    def fetch_html(self):
        html_pages = []

        with browser_context() as context:
            search_page = open_page(context, self.search_url)
            search_page.wait_for_timeout(random.choice([2000, 5000]))  # Random wait to mimic human behavior
            next_page = get_next_page_url(search_page)
            html_pages.append(get_rendered_html(search_page))
            while next_page:
                logger.info(f"Navigating to next page: {next_page}")
                search_page.goto(next_page, wait_until="domcontentloaded", timeout=60000)
                search_page.wait_for_timeout(random.choice([2000, 5000]))  # Random wait to mimic human behavior

                html_pages.append(get_rendered_html(search_page))
                next_page = get_next_page_url(search_page)
            close_page(search_page)

        folder = Path(self.storage_path)
        folder.mkdir(parents=True, exist_ok=True)
        for i, html in enumerate(html_pages):
            file_path = folder / f"bienici_playwright_{i+1}.html"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(html)