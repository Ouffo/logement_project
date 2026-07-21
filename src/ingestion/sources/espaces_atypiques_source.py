import random
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.browser_client import browser_context, close_page, get_rendered_html, open_page
from src.ingestion.sources.base import RentalListingSource
from src.processing.parsers import parse_price, parse_surface
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM
from src.storage.repository import clean_htmls
from src.utils.logger import logger
from src.utils.scrapping import (
    EXTRA_POSTAL_CODES_PATTERN,
    FloorInfo,
    city_from_postal_code,
    get_next_page_url,
    has_clear_view,
    parse_floor_info,
)

CARDINAL_WORDS = {
    "un": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "treize": 13,
    "quatorze": 14,
    "quinze": 15,
    "seize": 16,
    "dix-sept": 17,
    "dix-huit": 18,
    "dix-neuf": 19,
    "vingt": 20,
}

_CARDINAL_WORDS_PATTERN = "|".join(CARDINAL_WORDS)


def infer_floor_from_building_height(text: str) -> int | None:
    # Fallback for listings without the structured "Étage" / "N étages dans
    # l'immeuble" fields (e.g. a house entry) but that still mention the
    # building's total height and "dernier étage" in prose.
    match = re.search(
        rf"immeuble[^.\n]{{0,40}}\bde\s+(\d+|{_CARDINAL_WORDS_PATTERN})\s+[eé]tages?\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = match.group(1).lower()
    return int(value) if value.isdigit() else CARDINAL_WORDS.get(value)


def parse_espaces_atypiques_floor_from_text(text: str | None) -> FloorInfo:
    if not text:
        return FloorInfo(floor=None, is_top_floor=None)

    floor = None
    is_top_floor = None
    for sentence in re.split(r"[.\n]", text):
        info = parse_floor_info(sentence)
        if floor is None:
            floor = info.floor
        if is_top_floor is None:
            is_top_floor = info.is_top_floor
        if floor is not None and is_top_floor is not None:
            break

    if floor is None and is_top_floor:
        floor = infer_floor_from_building_height(text)

    return FloorInfo(floor=floor, is_top_floor=is_top_floor)


def parse_espaces_atypiques_postal_code(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(rf"\b(75\d{{3}}|{EXTRA_POSTAL_CODES_PATTERN})\b", text)
    return match.group(1) if match else None


def parse_espaces_atypiques_search_html(
    html: str,
    source: str = "espaces_atypiques",
    is_rental: bool = True,
) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    listings = []
    seen_ids = set()

    for card in soup.select("div.preview-annonce"):
        fav_el = card.select_one(".picto.favori[data-post-id]")
        source_id = fav_el.get("data-post-id") if fav_el else None

        if not source_id or source_id in seen_ids:
            continue

        seen_ids.add(source_id)

        link_el = card.select_one("a[href]")
        if not link_el:
            logger.info(f"Skipping espaces_atypiques listing without url: {source_id}")
            continue

        url = link_el.get("href")

        image_el = card.select_one("img")
        image_url = (image_el.get("data-src") or image_el.get("src")) if image_el else None

        title_el = card.select_one(".titre a")
        # The city+postal span also carries the "orange" class (shared with
        # the price span), so the price/surface spans must be excluded by
        # class rather than matched positively.
        localisation_el = card.select_one(".info.localisation")
        price_el = card.select_one(".info.orange:not(.localisation)")
        surface_el = card.select_one(".infos > .info:not(.localisation):not(.orange)")

        if not title_el or not price_el:
            logger.info(f"Skipping malformed espaces_atypiques listing: {source_id}")
            continue

        title = title_el.get_text(" ", strip=True)
        localisation_text = localisation_el.get_text(" ", strip=True) if localisation_el else None

        price_eur = parse_price(price_el.get_text(" ", strip=True))
        surface_m2 = parse_surface(surface_el.get_text(" ", strip=True)) if surface_el else None

        if not surface_m2 or not price_eur:
            logger.info(f"Skipping espaces_atypiques listing without surface/price: {source_id}")
            continue

        postal_code = parse_espaces_atypiques_postal_code(localisation_text)
        city = city_from_postal_code(postal_code)

        # Rooms/bedrooms aren't shown on the search card at all (only on
        # the detail page's characteristics list) — left for enrich_listing.
        # The title is the only text available at this stage (no
        # description on the card), but it can still mention "dernier
        # étage" or "calme" so it's still worth scanning.
        floor_info = parse_espaces_atypiques_floor_from_text(title)

        listing = RentalListing(
            source=source,
            source_id=source_id,
            url=url,
            title=title,
            description=None,
            city=city,
            postal_code=postal_code,
            address=None,
            district_name=localisation_text,
            price_eur=price_eur,
            surface_m2=surface_m2,
            rooms=None,
            bedrooms=None,
            is_rental=is_rental,
            floor=floor_info.floor,
            is_top_floor=floor_info.is_top_floor,
            furnished=("meublé" in title.lower() or "meublée" in title.lower()),
            parking="parking" in title.lower(),
            quiet=("calme" in title.lower() or "silencieux" in title.lower()),
            clear_view=has_clear_view(title),
            posted_at=None,
            image_url=image_url,
        )

        listings.append(listing)

    return listings


def get_espaces_atypiques_info_items(section):
    return section.select("div.info-content li")


def parse_espaces_atypiques_energy_class(section) -> str | None:
    # The DPE gauge marks the current band with an "active" class, unlike
    # Century21's SVG-only rendering or Maison et Appartement's CSS-class
    # letter suffix — the letter is directly readable here.
    label = section.select_one("li.classe-cep.active .lettre-cep")
    return label.get_text(strip=True) if label else None


def parse_espaces_atypiques_construction_year(section):
    # Not exposed anywhere (structured fields or free text) on this site's
    # detail pages at the time this was written.
    return None


def parse_espaces_atypiques_posted_at(section):
    # Not exposed anywhere on this site's detail pages at the time this was
    # written.
    return None


def parse_espaces_atypiques_rooms(section) -> int | None:
    for item in get_espaces_atypiques_info_items(section):
        match = re.match(r"(\d+)\s*pi[eè]ces?", item.get_text(" ", strip=True), flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def parse_espaces_atypiques_bedrooms(section) -> int | None:
    for item in get_espaces_atypiques_info_items(section):
        match = re.match(r"(\d+)\s*chambres?", item.get_text(" ", strip=True), flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def parse_espaces_atypiques_floor(section) -> FloorInfo:
    floor = None
    total_floors = None

    for item in get_espaces_atypiques_info_items(section):
        text = item.get_text(" ", strip=True)

        if floor is None:
            match = re.match(r"[eé]tage\s*:\s*(\d+)", text, flags=re.IGNORECASE)
            if match:
                floor = int(match.group(1))
                continue

        if total_floors is None:
            match = re.match(
                r"(\d+)\s+[eé]tages?\s+dans\s+l['’]immeuble", text, flags=re.IGNORECASE
            )
            if match:
                total_floors = int(match.group(1))

    is_top_floor = None
    if floor is not None and total_floors is not None:
        is_top_floor = floor == total_floors

    if floor is None:
        # A house/atypical listing without the structured "Étage" field —
        # fall back to the free-text description.
        description_el = section.select_one("#annonce-description")
        description = description_el.get_text(" ", strip=True) if description_el else None
        text_info = parse_espaces_atypiques_floor_from_text(description)
        floor = text_info.floor
        if is_top_floor is None:
            is_top_floor = text_info.is_top_floor

    return FloorInfo(floor=floor, is_top_floor=is_top_floor)


class EspacesAtypiquesSource(RentalListingSource):
    name = "espaces_atypiques"
    search_url = "https://www.espaces-atypiques.com/locations/?pl=511%2C2347%2C1081&pmin&pmax=1200&type=12&smin=25&smax&q&order=ddesc"
    storage_path = "data/raw/espaces_atypiques_htmls"
    detail_storage_path = "data/raw/espaces_atypiques_details_htmls"
    parser = staticmethod(parse_espaces_atypiques_search_html)

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
            file_path = folder / f"espaces_atypiques_playwright_{i + 1}.html"
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(html)

    def fetch_detail_htmls(
        self,
        listings: list[RentalListingORM],
    ) -> list[tuple[RentalListingORM, str]]:
        detail_pages = []
        folder = Path(self.detail_storage_path)
        fetched_count = 0

        with browser_context() as context:
            for listing in listings:
                source_id = listing.source_id
                if not (folder / f"{source_id}.html").exists():
                    print(f"opening {listing.url}")
                    page = open_page(context, str(listing.url))
                    page.wait_for_timeout(random.choice([5000, 10000]))

                    detail_pages.append((listing, get_rendered_html(page)))

                    close_page(page)
                    fetched_count += 1

                    # Same anti-bot rate limiting risk observed on
                    # maisonsetappartements.fr after too many rapid
                    # sequential detail-page fetches — space requests out
                    # defensively here too.
                    if fetched_count % 15 == 0:
                        pause_seconds = random.uniform(30, 60)
                        logger.info(
                            f"Pausing {pause_seconds:.0f}s after {fetched_count} "
                            "detail page fetches to avoid rate limiting"
                        )
                    else:
                        pause_seconds = random.uniform(4, 9)
                    time.sleep(pause_seconds)
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
        soup = BeautifulSoup(html, "html.parser")

        listing.energy_class = parse_espaces_atypiques_energy_class(section=soup)
        listing.construction_year = parse_espaces_atypiques_construction_year(section=soup)
        listing.posted_at = parse_espaces_atypiques_posted_at(section=soup)

        rooms = parse_espaces_atypiques_rooms(section=soup)
        if rooms is not None:
            listing.rooms = rooms

        bedrooms = parse_espaces_atypiques_bedrooms(section=soup)
        if bedrooms is not None:
            listing.bedrooms = bedrooms

        floor_info = parse_espaces_atypiques_floor(section=soup)
        listing.floor = floor_info.floor
        listing.is_top_floor = floor_info.is_top_floor

        # The search card has no description at all — the detail page's is
        # the only one available, and also the only chance to catch
        # furnished/parking/quiet/clear_view (title-only at parse time).
        description_el = soup.select_one("#annonce-description")
        full_description = description_el.get_text(" ", strip=True) if description_el else None
        if full_description:
            if not listing.description or len(full_description) > len(listing.description):
                listing.description = full_description

            lowered = full_description.lower()
            if not listing.furnished and ("meublé" in lowered or "meublée" in lowered):
                listing.furnished = True
            if not listing.parking and "parking" in lowered:
                listing.parking = True
            if not listing.quiet and ("calme" in lowered or "silencieux" in lowered):
                listing.quiet = True
            if has_clear_view(full_description):
                listing.clear_view = True

        listing.details_fetched_at = datetime.now(UTC)


def parse_espaces_atypiques_sale_search_html(html: str) -> list[RentalListing]:
    return parse_espaces_atypiques_search_html(
        html, source="espaces_atypiques_sale", is_rental=False
    )


class EspacesAtypiquesSaleSource(EspacesAtypiquesSource):
    name = "espaces_atypiques_sale"
    search_url = (
        "https://www.espaces-atypiques.com/ventes/?pl=511&radius=0&pmin&pmax=650000"
        "&type=12&smin=50&smax&q&order=ddesc"
    )
    storage_path = "data/raw/espaces_atypiques_sale_htmls"
    detail_storage_path = "data/raw/espaces_atypiques_sale_details_htmls"
    parser = staticmethod(parse_espaces_atypiques_sale_search_html)
