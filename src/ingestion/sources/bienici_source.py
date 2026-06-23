import random
import re
from datetime import UTC, datetime
from bs4 import BeautifulSoup
from pathlib import Path
from src.storage.repository import clean_htmls
from src.ingestion.browser_client import browser_context, close_page, get_rendered_html, open_page
from src.ingestion.sources.base import RentalListingSource
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM
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

FRENCH_MONTHS = {
    "janvier": 1, "janv": 1, "janv.": 1,
    "février": 2, "fevrier": 2, "févr": 2, "févr.": 2, "fevr": 2, "fevr.": 2,
    "mars": 3,
    "avril": 4, "avr": 4, "avr.": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7, "juil.": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sept": 9, "sept.": 9,
    "octobre": 10, "oct": 10, "oct.": 10,
    "novembre": 11, "nov": 11, "nov.": 11,
    "décembre": 12, "decembre": 12, "déc": 12, "déc.": 12, "dec": 12, "dec.": 12,
}


def parse_bienici_posted_at(section) -> datetime | None:
    text = section.get_text("\n", strip=True)

    match = re.search(
        r"Publiée?\s+le\s+(\d{1,2})\s+([a-zéûîôàèùç.]+)\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2).lower()
    year = int(match.group(3))

    month = FRENCH_MONTHS.get(month_name)

    if month is None:
        return None

    return datetime(year, month, day, tzinfo=UTC)

ENERGY_CLASSES = {"A", "B", "C", "D", "E", "F", "G"}


def get_bienici_energy_section(section):
    return section.select_one("section.energySection")


def parse_bienici_energy_class(section) -> str | None:
    energy_section = get_bienici_energy_section(section)

    if energy_section is None:
        return None

    if is_bienici_energy_not_submitted(energy_section):
        return None

    return (
        parse_bienici_energy_class_from_rating(energy_section)
        or parse_bienici_energy_class_from_json(energy_section)
        or parse_bienici_energy_class_from_score(energy_section)
    )


def is_bienici_energy_not_submitted(energy_section) -> bool:
    text = energy_section.get_text("\n", strip=True).lower()
    return "non soumis" in text


def parse_bienici_energy_class_from_rating(energy_section) -> str | None:
    selectors = [
        ".energy-diagnostic__dpe .energy-diagnostic-rating__classification",
        ".dpe-line__classification",
        ".energy-consumption__classification",
    ]

    for selector in selectors:
        element = energy_section.select_one(selector)

        if not element:
            continue

        text = element.get_text(" ", strip=True).upper()

        match = re.search(r"\b([A-G])\b", text)

        if match:
            return match.group(1)

    return None

def parse_bienici_energy_class_from_json(energy_section) -> str | None:
    html = str(energy_section)

    patterns = [
        r'"energyClass"\s*:\s*"([A-G])"',
        r'"energy_class"\s*:\s*"([A-G])"',
        r'"dpe"\s*:\s*"([A-G])"',
        r'"dpeClass"\s*:\s*"([A-G])"',
        r'"dpe_class"\s*:\s*"([A-G])"',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)

        if match:
            return match.group(1).upper()

    return None


def parse_bienici_energy_class_from_score(energy_section) -> str | None:
    score = parse_bienici_dpe_score(energy_section)

    if score is None:
        return None

    return energy_class_from_dpe_score(score)


def parse_bienici_dpe_score(energy_section) -> int | None:
    text = energy_section.get_text("\n", strip=True)

    if "énergie finale" in text.lower() or "energie finale" in text.lower():
        return None

    patterns = [
        r"Consommation\s+énergétique.*?(\d{2,4})\s*kWh",
        r"Performance\s+énergétique.*?(\d{2,4})\s*kWh",
        r"Diagnostic\s+de\s+Performance\s+Énergétique.*?(\d{2,4})\s*kWh",
        r"DPE.*?(\d{2,4})\s*kWh",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if match:
            return int(match.group(1))

    return None


def energy_class_from_dpe_score(score: int) -> str:
    if score <= 70:
        return "A"
    if score <= 110:
        return "B"
    if score <= 180:
        return "C"
    if score <= 250:
        return "D"
    if score <= 330:
        return "E"
    if score <= 420:
        return "F"
    return "G"

def parse_bienici_construction_year(section) -> int | None:
    text = section.get_text("\n", strip=True)

    patterns = [
        r"année\s+de\s+construction\s*[:\-]?\s*(\d{4})",
        r"construction\s*[:\-]?\s*(\d{4})",
        r"construit\s+en\s+(\d{4})",
        r"immeuble\s+de\s+(\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            year = int(match.group(1))
            if 1700 <= year <= datetime.now().year + 1:
                return year

    return None


FRENCH_MONTHS = {
    "janvier": 1, "janv": 1, "janv.": 1,
    "février": 2, "fevrier": 2, "févr": 2, "févr.": 2, "fevr": 2, "fevr.": 2,
    "mars": 3,
    "avril": 4, "avr": 4, "avr.": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7, "juil.": 7,
    "août": 8, "aout": 8,
    "septembre": 9, "sept": 9, "sept.": 9,
    "octobre": 10, "oct": 10, "oct.": 10,
    "novembre": 11, "nov": 11, "nov.": 11,
    "décembre": 12, "decembre": 12, "déc": 12, "déc.": 12, "dec": 12, "dec.": 12,
}

def parse_bienici_posted_at(section) -> datetime | None:
    text = section.get_text("\n", strip=True)

    match = re.search(
        r"Publiée?\s+le\s+(\d{1,2})\s+([a-zéûîôàèùç.]+)\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2).lower()
    year = int(match.group(3))

    month = FRENCH_MONTHS.get(month_name)

    if month is None:
        return None

    return datetime(year, month, day, tzinfo=UTC)

class BieniciSource(RentalListingSource):
    name = "bienici"
    search_url = "https://www.bienici.com/recherche/location/paris-75000/appartement/1-piece-et-plus?prix-max=1200&surface-min=25"
    storage_path = "data/raw/bienici_htmls"
    detail_storage_path = "data/raw/bienici_details_htmls"
    parser = staticmethod(parse_bienici_search_html)

    def __init__(self, max_listings: int | None = None):
        self.max_listings = max_listings

    def fetch_html(self):
        clean_htmls(self.storage_path)
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

    def fetch_detail_htmls(
        self,
        listings: list[RentalListingORM],
    ) -> list[tuple[RentalListingORM, str]]:
        detail_pages = []
        folder = Path(self.detail_storage_path)

        with browser_context() as context:
            for listing in listings:
                source_id = listing.source_id
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

        soup = BeautifulSoup(html, "html.parser")
        section = soup.select_one(f"section#section-detailedSheet_{listing.source_id}")

        if section is None:
            logger.warning(f"Detail section not found for bienici listing {listing.source_id}")
            listing.details_fetched_at = datetime.now(UTC)
            return

        listing.energy_class = parse_bienici_energy_class(section=section)
        listing.construction_year = parse_bienici_construction_year(section=section)
        listing.posted_at = parse_bienici_posted_at(section=section)
        listing.details_fetched_at = datetime.now(UTC)
        print(f"url: {listing.url}, posted date: {listing.posted_at}")