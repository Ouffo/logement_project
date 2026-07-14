import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.browser_client import (
    browser_context,
    close_page,
    get_rendered_html,
    open_page,
)
from src.processing.parsers import parse_price, parse_surface
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM
from src.storage.repository import clean_htmls
from src.utils.logger import logger
from src.utils.scrapping import (
    EXTRA_CITY_NAMES_PATTERN,
    EXTRA_POSTAL_CODES_PATTERN,
    city_from_postal_code,
    get_next_page_url,
    parse_floor,
)

from .base import RentalListingSource


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
        r"(\d+(?:[,.]\d+)?)\s*m[²2]",
        text,
        flags=re.IGNORECASE,
    )

    if surface_match:
        surface_m2 = parse_surface(surface_match.group(0))

    return rooms, surface_m2


def parse_location(text: str) -> tuple[str, str | None]:
    match = re.search(
        rf"(Paris|{EXTRA_CITY_NAMES_PATTERN})\s+(75\d{{3}}|{EXTRA_POSTAL_CODES_PATTERN})(?:\s+([^\n]+))?",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return "Paris", None

    postal_code = match.group(2)

    return city_from_postal_code(postal_code), postal_code


def parse_source_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def extract_subject_by_source_id(html: str) -> dict[str, str]:
    pattern = re.compile(
        r'"list_id"\s*:\s*(\d+).*?'
        r'"subject"\s*:\s*"([^"]+)"',
        flags=re.DOTALL,
    )

    return {source_id: subject for source_id, subject in pattern.findall(html)}


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


def parse_leboncoin_floor(html: str) -> int | None:
    # 1. Le plus fiable : JSON embarqué Leboncoin
    match = re.search(r'"key"\s*:\s*"floor_number"\s*,\s*"value"\s*:\s*"(-?\d+)"', html)
    if match:
        return int(match.group(1))

    soup = BeautifulSoup(html, "html.parser")

    # 2. Fallback DOM visible (champ structuré "Étage de votre bien")
    block = soup.select_one('div[title="Étage de votre bien"]')
    if block:
        value = block.get_text(strip=True)
        if value.upper() == "RDC":
            return 0
        if re.fullmatch(r"-?\d+", value):
            return int(value)

    # 3. Fallback texte libre : certaines annonces ne renseignent l'étage
    # que dans la description, pas dans le champ structuré ci-dessus.
    description_el = soup.select_one('[data-qa-id="adview_description_container"]')
    if description_el:
        floor = parse_floor(description_el.get_text(" ", strip=True))
        if floor is not None:
            return floor

    return None


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


def parse_leboncoin_posted_at(html: str) -> datetime | None:
    return parse_leboncoin_posted_at_from_json(html) or parse_leboncoin_posted_at_from_visible_text(
        html
    )


def parse_leboncoin_posted_at_from_json(html: str) -> datetime | None:
    for field in ["index_date", "first_publication_date"]:
        match = re.search(
            rf'"{field}"\s*:\s*"(\d{{4}}-\d{{2}}-\d{{2}})\s+(\d{{2}}):(\d{{2}}):(\d{{2}})"',
            html,
        )

        if match:
            return datetime(
                int(match.group(1)[0:4]),
                int(match.group(1)[5:7]),
                int(match.group(1)[8:10]),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
                tzinfo=UTC,
            )

    return None


def parse_leboncoin_posted_at_from_visible_text(html: str) -> datetime | None:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    match = re.search(
        r"(aujourd'hui|hier|\d{1,2}/\d{1,2}/\d{4})\s+à\s+(?:\d{1,2}\s+heures?\s+\d{2}|(\d{1,2}):(\d{2}))",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    date_part = match.group(1).lower()
    today = datetime.now(UTC).date()

    if date_part == "aujourd'hui":
        date_value = today
    elif date_part == "hier":
        date_value = today - timedelta(days=1)
    else:
        date_value = datetime.strptime(date_part, "%d/%m/%Y").date()

    time_match = re.search(r"(\d{1,2}):(\d{2})", match.group(0))
    if not time_match:
        time_match = re.search(r"(\d{1,2})\s+heures?\s+(\d{2})", match.group(0))

    if not time_match:
        return None

    return datetime(
        date_value.year,
        date_value.month,
        date_value.day,
        int(time_match.group(1)),
        int(time_match.group(2)),
        tzinfo=UTC,
    )


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

        url = f"https://www.leboncoin.fr{href}" if href.startswith("/") else href

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
            rf"(Paris|{EXTRA_CITY_NAMES_PATTERN})\s+(75\d{{3}}|{EXTRA_POSTAL_CODES_PATTERN})([^\n]*)",
            text,
            flags=re.IGNORECASE,
        )

        postal_code = None
        district_name = None
        city = "Paris"

        if location_match:
            city_name = location_match.group(1)
            postal_code = location_match.group(2)
            district_name = (f"{city_name} {postal_code}{location_match.group(3)}").strip()
            city = city_from_postal_code(postal_code)

        image_el = article.select_one("img[src]")
        image_url = image_el.get("src") if image_el else None

        source_id = url.rstrip("/").split("/")[-1]

        title = article.get("aria-label") or f"{property_type} {rooms} pièce(s) {surface_m2} m²"

        if surface_m2 is None or surface_m2 <= 0:
            logger.info(f"Skipping listing without surface: {url}")
            continue

        listing = RentalListing(
            source="leboncoin",
            source_id=source_id,
            url=url,
            title=title,
            description=subject_by_id.get(source_id),
            city=city,
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
    search_url = "https://www.leboncoin.fr/recherche?category=8&locations=Saint-Cyr-l%27Ecole_78210__48.79981_2.06753_2578,Issy-les-Moulineaux_92130__48.82123_2.25161_2827,V%C3%A9lizy-Villacoublay_78140__48.78503_2.18247_3771,Paris__48.86017419624389_2.337177366534126_9370&price=800-1200"
    storage_path = "data/raw/leboncoin_htmls"
    detail_storage_path = "data/raw/leboncoin_details_htmls"
    parser = staticmethod(parse_leboncoin_search_html)

    def __init__(self, max_listings: int | None = None):
        self.max_listings = max_listings

    def fetch_html(self):
        clean_htmls(self.storage_path)
        html_pages = []

        with browser_context() as context:
            search_page = open_page(context, self.search_url)
            search_page.wait_for_timeout(
                random.choice([2000, 5000])
            )  # Random wait to mimic human behavior
            next_page = get_next_page_url(search_page)
            html_pages.append(get_rendered_html(search_page))
            while next_page:
                logger.info(f"Navigating to next page: {next_page}")
                search_page.goto(next_page, wait_until="domcontentloaded", timeout=60000)
                search_page.wait_for_timeout(
                    random.choice([2000, 5000])
                )  # Random wait to mimic human behavior

                html_pages.append(get_rendered_html(search_page))
                next_page = get_next_page_url(search_page)
            close_page(search_page)

        folder = Path(self.storage_path)
        folder.mkdir(parents=True, exist_ok=True)
        for i, html in enumerate(html_pages):
            file_path = folder / f"leboncoin_playwright_{i + 1}.html"
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

                    detail_pages.append((listing, get_rendered_html(page)))

                    close_page(page)
                else:
                    print(f"reading html {source_id}.html")
                    file_path = Path(folder / f"{source_id}.html")
                    html = file_path.read_text(encoding="utf-8")
                    detail_pages.append((listing, html))

        return detail_pages

    def enrich_listing(
        self,
        listing: RentalListingORM,
        html: str,
    ) -> None:

        listing.energy_class = parse_leboncoin_energy(html)
        listing.construction_year = parse_leboncoin_construction_year(html)
        listing.posted_at = parse_leboncoin_posted_at(html)
        listing.floor = parse_leboncoin_floor(html)
        listing.details_fetched_at = datetime.now(UTC)
        print(f"url: {listing.url}, posted date: {listing.posted_at}")
