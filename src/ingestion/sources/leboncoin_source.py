from pathlib import Path
import re
import random
from datetime import UTC, datetime
from src.utils.logger import logger
from src.utils.scrapping import get_next_page_url
from src.processing.parsers import parse_french_posted_at, parse_price, parse_surface
from .base import RentalListingSource
from src.ingestion.browser_client import (
    browser_context,
    open_page,
    get_rendered_html,
    close_page,
)
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM
from bs4 import BeautifulSoup

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


def  parse_source_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1]

def extract_subject_by_source_id(html: str) -> dict[str, str]:
    pattern = re.compile(
        r'"list_id"\s*:\s*(\d+).*?'
        r'"subject"\s*:\s*"([^"]+)"',
        flags=re.DOTALL,
    )

    return {
        source_id: subject
        for source_id, subject in pattern.findall(html)
    }

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

        image_url = get_meta_content(
            section,
            'meta[property="og:image"]',
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

        posted_at = parse_french_posted_at(full_text)

        logger.info(f"rooms : {rooms}, surface_m2 : {surface_m2}")
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
            image_url=image_url,
            posted_at=posted_at,
            relevance_score=None,
        )

        listings.append(listing)

    return listings

def parse_property_type(text: str) -> str | None:
    match = re.search(
        r"\b(Appartement|Studio|Loft|Duplex)\b",
        text,
        flags=re.IGNORECASE,
    )
    return match.group(1).title() if match else None


def parse_rooms(text: str) -> int | None:
    match = re.search(
        r"(\d+)\s*pi[eè]ce[s]?",
        text,
        flags=re.IGNORECASE,
    )
    return int(match.group(1)) if match else None

def parse_surface_m2(text: str) -> float | None:
    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*m[²2]",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    return float(match.group(1).replace(",", "."))


ENERGY_CLASSES = {"A", "B", "C", "D", "E", "F", "G"}


def parse_leboncoin_energy_class(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    # Cas texte visible :
    # "Classe énergie : D"
    # "DPE : E"
    # "Diagnostic de performance énergétique : C"
    patterns = [
        r"classe\s+énergie\s*[:\-]?\s*([A-G])\b",
        r"classe\s+energetique\s*[:\-]?\s*([A-G])\b",
        r"classe\s+énergétique\s*[:\-]?\s*([A-G])\b",
        r"\bDPE\s*[:\-]?\s*([A-G])\b",
        r"diagnostic\s+de\s+performance\s+énergétique\s*[:\-]?\s*([A-G])\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            return match.group(1).upper()

    # Fallback JSON / scripts
    return parse_energy_class_from_json_like_text(html)


def parse_leboncoin_energy(html: str) -> str | None:
    # 1. Le plus fiable : JSON embarqué Leboncoin
    patterns = [
        r'"key"\s*:\s*"energy_rate"\s*,\s*"value"\s*:\s*"([a-g])"',
        r'"key"\s*:\s*"energy_rate".{0,300}?"value"\s*:\s*"([a-g])"',
        r'"key_label"\s*:\s*"Classe énergie".{0,300}?"value"\s*:\s*"([a-g])"',
        r'"key_label"\s*:\s*"Classe énergie".{0,300}?"value_label"\s*:\s*"([A-G])"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).upper()

    # 2. Fallback DOM visible
    soup = BeautifulSoup(html, "html.parser")

    block = soup.select_one('[data-qa-id="criteria_item_energy_rate"]')
    if block:
        texts = [t.strip() for t in block.stripped_strings]
        for text in texts:
            value = text.upper()
            if value in ENERGY_CLASSES:
                return value

    return None

def parse_energy_class_from_json_like_text(html: str) -> str | None:
    patterns = [
        r'"energy_class"\s*:\s*"([A-G])"',
        r'"energyClass"\s*:\s*"([A-G])"',
        r'"dpe"\s*:\s*"([A-G])"',
        r'"ges"\s*:\s*"([A-G])"',  # à éviter si tu veux uniquement énergie, mais utile debug
        r'"energy"\s*:\s*"([A-G])"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)

        if match:
            value = match.group(1).upper()

            if value in ENERGY_CLASSES:
                return value

    return None

def parse_leboncoin_construction_year(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    patterns = [
        r"année\s+de\s+construction\s*[:\-]?\s*(\d{4})",
        r"année\s+construction\s*[:\-]?\s*(\d{4})",
        r"construction\s*[:\-]?\s*(\d{4})",
        r"construit\s+en\s+(\d{4})",
        r"immeuble\s+de\s+(\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            year = int(match.group(1))

            if is_plausible_construction_year(year):
                return year

    return parse_construction_year_from_json_like_text(html)


def parse_construction_year_from_json_like_text(html: str) -> int | None:
    patterns = [
        r'"construction_year"\s*:\s*(\d{4})',
        r'"constructionYear"\s*:\s*(\d{4})',
        r'"yearOfConstruction"\s*:\s*(\d{4})',
        r'"buildingYear"\s*:\s*(\d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)

        if match:
            year = int(match.group(1))

            if is_plausible_construction_year(year):
                return year

    return None


def is_plausible_construction_year(year: int) -> bool:
    return 1700 <= year <= 2030


def parse_leboncoin_search_html(html: str) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    subject_by_id = extract_subject_by_source_id(html)

    listings = []
    seen_urls = set()

    for article in soup.select("article"):
        link_el = article.select_one("a[href*='/ad/locations/']")

        if link_el is None:
            continue

        href = link_el.get("href")

        if not href:
            continue

        url = (
            f"https://www.leboncoin.fr{href}"
            if href.startswith("/")
            else href
        )

        if url in seen_urls:
            continue

        seen_urls.add(url)

        text = article.get_text("\n", strip=True)

        combined_text = text + " " + subject_by_id.get(parse_source_id(url), "")

        property_type = parse_property_type(combined_text)
        rooms = parse_rooms(combined_text)
        surface_m2 = parse_surface_m2(combined_text)


        if not property_type:
            logger.info(f"Skipping listing without property type: {url}")
            continue

        # Premier prix visible
        price_match = re.search(
            r"(\d[\d\s\u202f\xa0]*€)",
            text,
        )

        if not price_match:
            logger.info(f"Skipping listing without price: {url}")
            continue

        price_eur = parse_price(price_match.group(1))

        location_match = re.search(
            r"Paris\s+(75\d{3})([^\n]*)",
            text,
            flags=re.IGNORECASE,
        )

        postal_code = None
        district_name = None

        if location_match:
            postal_code = location_match.group(1)
            district_name = (
                f"Paris {postal_code}"
                f"{location_match.group(2)}"
            ).strip()

        image_el = article.select_one("img[src]")
        image_url = image_el.get("src") if image_el else None

        source_id = url.rstrip("/").split("/")[-1]

        title = (
            article.get("aria-label")
            or f"{property_type} {rooms} pièce(s) {surface_m2} m²"
        )

        if surface_m2 is None or surface_m2 <= 0:
            logger.info(f"Skipping listing without surface: {url}")
            continue

        listing = RentalListing(
            source="leboncoin",
            source_id=source_id,
            url=url,
            title=title,
            description=subject_by_id.get(source_id),
            city="Paris",
            postal_code=postal_code,
            address=None,
            district_name=district_name,
            latitude=None,
            longitude=None,
            price_eur=price_eur,
            surface_m2=surface_m2,
            rooms=rooms,
            bedrooms=None,
            furnished="meublé" in text.lower(),
            parking="parking" in text.lower(),
            quiet=False,
            posted_at=None,
            relevance_score=None,
            image_url=image_url,
        )

        listings.append(listing)

    return listings

class LeboncoinSource(RentalListingSource):
    name = "leboncoin"
    search_url = "https://www.leboncoin.fr/recherche?category=8&locations=Paris__48.86017419624389_2.337177366534126_9370&price=800-1200"
    storage_path = "data/raw/leboncoin_htmls"
    detail_storage_path = "data/raw/leboncoin_details_htmls"
    parser = staticmethod(parse_leboncoin_search_html)

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
            file_path = folder / f"leboncoin_playwright_{i+1}.html"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(html)

    def fetch_detail_htmls(
        self,
        listings: list[RentalListingORM],
    ) -> list[tuple[RentalListingORM, str]]:
        detail_pages = []
        folder = Path(self.detail_storage_path)

        with browser_context() as context:
            for listing in listings:
                source_id = listing.url.rstrip("/").split("/")[-1]
                if not (folder / f"{source_id}.html").exists():
                    print(f"opening {listing.url}")
                    page = open_page(context, str(listing.url))
                    page.wait_for_timeout(random.choice([5000, 10000]))

                    detail_pages.append(
                        (listing, get_rendered_html(page))
                    )

                    close_page(page)
                else:
                    print(f"reading html {source_id}.html")
                    file_path = Path(folder / f"{source_id}.html")
                    html = file_path.read_text(encoding="utf-8")
                    detail_pages.append(
                        (listing, html)
                    )

        return detail_pages
    
    def enrich_listing(
        self,
        listing: RentalListingORM,
        html: str,
    ) -> None:

        listing.energy_class = parse_leboncoin_energy(html)
        listing.construction_year = parse_leboncoin_construction_year(html)
        listing.details_fetched_at = datetime.now(UTC)
        print(f"url: {listing.url}, energy class: {listing.energy_class}, construction data: {listing.construction_year}")