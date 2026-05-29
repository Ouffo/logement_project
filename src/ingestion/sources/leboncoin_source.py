import re
from src.utils.logger import logger
from src.utils.scrapping import combine_htmls, get_next_page_url
from src.processing.parsers import parse_price, parse_surface
from .base import RentalListingSource
from src.ingestion.browser_client import (
    browser_context,
    open_page,
    get_rendered_html,
    close_page,
)
from src.storage.models import RentalListing
from bs4 import BeautifulSoup


class LeboncoinSource(RentalListingSource):
    name = "leboncoin"
    search_url = "https://www.leboncoin.fr/recherche?category=8&locations=Paris__48.86017419624389_2.337177366534126_9370&price=800-1200"

    def __init__(self, max_listings: int | None = None):
        self.max_listings = max_listings

    def fetch_listings(self) -> list[RentalListing]:
        with browser_context() as context:
            search_page = open_page(context, self.search_url)
            next_page = get_next_page_url(search_page)

            urls = collect_leboncoin_listing_urls(search_page)
            
            while next_page:
                logger.info(f"Navigating to next page: {next_page}")
                search_page.goto(next_page, wait_until="domcontentloaded", timeout=60000)
                urls.extend(collect_leboncoin_listing_urls(search_page))
                next_page = get_next_page_url(search_page)
            close_page(search_page)

            html_pages = []

            urls = list(dict.fromkeys(urls))  # Remove duplicates

            if self.max_listings is not None:
                urls = urls[:self.max_listings]
            logger.info(f"Found {len(urls)} listing URLs, fetching details...")
            for url in urls:
                page = open_page(context, url)
                page.wait_for_timeout(1000)
                html = get_rendered_html(page)
                html_pages.append((url, html))
                close_page(page)

            html = combine_htmls(html_pages)
            with open(f"data/raw/leboncoin.html", "w", encoding="utf-8") as file:
                file.write(html)

            return parse_leboncoin_html(html)


def collect_leboncoin_listing_urls(page) -> list[str]:
    cards = page.locator("a[href*='/ad/locations/']")
    urls = []
    seen = set()

    for i in range(cards.count()):
        href = cards.nth(i).get_attribute("href")

        if not href or href in seen:
            continue

        seen.add(href)

        if href.startswith("/"):
            href = f"https://www.leboncoin.fr{href}"

        urls.append(href)

    return urls

def get_meta_content(section, selector: str) -> str | None:
    el = section.select_one(selector)

    if el is None:
        return None

    return el.get("content")


def parse_rooms_and_surface(text: str) -> tuple[int | None, float | None]:
    rooms = None
    surface_m2 = None

    rooms_match = re.search(
        r"(\d+)\s*pi[eè]ce",
        text,
        flags=re.IGNORECASE,
    )

    if rooms_match:
        rooms = int(rooms_match.group(1))

    surface_match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*m²",
        text,
        flags=re.IGNORECASE,
    )

    if surface_match:
        surface_m2 = parse_surface(
            surface_match.group(0)
        )

    return rooms, surface_m2


def parse_location(text: str) -> tuple[str, str | None]:
    match = re.search(
        r"Paris\s+(75\d{3})(?:\s+([^\n]+))?",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return "Paris", None

    postal_code = match.group(1)
    district_name = match.group(2)

    return "Paris", postal_code


def parse_source_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def parse_leboncoin_html(html: str) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")
    apartment_keywords = ["appartement", "studio", "loft", "duplex", "meublé", "pièce"]

    listings = []

    for section in soup.select("section.listing-detail"):
        url = section.get("data-url")

        if not url:
            logger.warning("Skipping listing without data-url")
            continue

        title = get_meta_content(
            section,
            'meta[property="og:title"]',
        )

        description = get_meta_content(
            section,
            'meta[property="og:description"]',
        )

        if not title:
            title_el = section.select_one("title")
            title = title_el.get_text(strip=True) if title_el else None

        full_text = section.get_text("\n", strip=True)


        logger.info(f"title : {title}")

        if not title or not any(keyword in title.lower() for keyword in apartment_keywords):
            logger.info(f"Skipping non-apartment listing: {url}")
            continue

        price_el = section.select_one(
            '[data-qa-id="adview_price"]'
        )

        if price_el is None:
            logger.warning(f"Skipping listing without price: {url}")
            continue

        price_text = price_el.get_text(" ", strip=True)

        rooms, surface_m2 = parse_rooms_and_surface(
            f"{title}\n{full_text}"
        )

        if surface_m2 is None:
            logger.warning(f"Skipping listing without surface: {url}")
            continue

        city, postal_code = parse_location(full_text)

        listing = RentalListing(
            source="leboncoin",
            source_id=parse_source_id(url),
            url=url,
            title=title,
            description=description,
            city=city,
            postal_code=postal_code,
            address=None,
            district_name=None,
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
        )

        listings.append(listing)

    return listings