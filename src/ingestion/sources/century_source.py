import random
import re
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

CENTURY_BASE_URL = "https://www.century21.fr"


def parse_century_search_html(
    html: str,
    source: str = "century",
    is_rental: bool = True,
) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    listings = []
    seen_ids = set()

    # Rental and sale search pages both render results with this card, unlike
    # the "biens similaires" carousel widget which uses a different (unsuffixed)
    # thumbnail class and must not be picked up here.
    for card in soup.select(".c-the-property-thumbnail-with-content[data-uid]"):
        source_id = card.get("data-uid")

        if not source_id or source_id in seen_ids:
            continue

        seen_ids.add(source_id)

        link_el = card.select_one("a[href]")
        if not link_el:
            logger.info(f"Skipping Century listing without url: {source_id}")
            continue

        href = link_el.get("href")
        url = href if href.startswith("http") else f"{CENTURY_BASE_URL}{href}"

        image_el = card.select_one("img[src]")
        image_url = None
        if image_el:
            src = image_el.get("src")
            image_url = src if src.startswith("http") else f"{CENTURY_BASE_URL}{src}"

        heading_el = card.select_one(".c-text-theme-heading-4")
        title_el = card.select_one(".c-text-theme-heading-3")
        price_el = card.select_one(".c-text-theme-heading-1")
        description_el = card.select_one(".c-text-theme-base")

        if not heading_el or not price_el:
            logger.info(f"Skipping malformed Century listing: {source_id}")
            continue

        heading_parts = list(heading_el.stripped_strings)
        if not heading_parts:
            logger.info(f"Skipping Century listing without location info: {source_id}")
            continue

        title = title_el.get_text(" ", strip=True) if title_el else None
        description = description_el.get_text(" ", strip=True) if description_el else None

        if not title:
            logger.info(f"Skipping Century listing without title: {source_id}")
            continue

        price_parts = list(price_el.stripped_strings)
        price_eur = parse_price(price_parts[0]) if price_parts else None

        heading_text = " ".join(heading_parts)
        surface_m2 = parse_century_surface(heading_text)
        rooms = parse_century_rooms(heading_text)

        if not surface_m2 or not price_eur:
            logger.info(f"Skipping Century listing without surface/price: {source_id}")
            continue

        postal_code = parse_century_postal_code(heading_parts[0])
        city = city_from_postal_code(postal_code)

        full_text = f"{title or ''}\n{description or ''}"

        listing = RentalListing(
            source=source,
            source_id=source_id,
            url=url,
            title=title,
            description=description,
            city=city,
            postal_code=postal_code,
            address=None,
            district_name=None,
            latitude=None,
            longitude=None,
            price_eur=price_eur,
            surface_m2=surface_m2,
            rooms=rooms,
            bedrooms=None,
            is_rental=is_rental,
            furnished=("meublé" in full_text.lower() or "meublée" in full_text.lower()),
            parking="parking" in full_text.lower(),
            quiet=("calme" in full_text.lower() or "silencieux" in full_text.lower()),
            clear_view=has_clear_view(full_text),
            posted_at=None,
            relevance_score=None,
            image_url=image_url,
        )

        listings.append(listing)

    return listings


def parse_century_surface(text: str) -> float | None:
    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*m\s*[²2]",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return parse_surface(match.group(0))


def parse_century_rooms(text: str) -> int | None:
    match = re.search(
        r"(\d+)\s*pi[eè]ce[s]?",
        text,
        flags=re.IGNORECASE,
    )

    return int(match.group(1)) if match else None


def parse_century_postal_code(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(rf"\b(75\d{{3}}|{EXTRA_POSTAL_CODES_PATTERN})\b", text)
    return match.group(1) if match else None


def get_century_global_view_items(section):
    return section.select(".c-the-property-detail-global-view__list li")


def parse_century_energy_class(section) -> str | None:
    dpe_section = section.select_one("section.c-the-property-detail-dpe")

    if dpe_section is None:
        return None

    chiffres = dpe_section.find("g", attrs={"data-name": "chiffres"})

    if chiffres is None:
        return None

    numbers = [t.get_text(strip=True) for t in chiffres.find_all("tspan")]

    if len(numbers) < 2:
        return None

    try:
        energy_score = int(re.sub(r"[^\d]", "", numbers[0]))
        ges_score = int(re.sub(r"[^\d]", "", numbers[1]))
    except ValueError:
        return None

    # Century21 only renders the DPE gauge as an SVG (no accessible letter
    # in the DOM), so the class is derived from the raw kWh/m².an and
    # kgCO2/m².an values using the official post-2021 bands; French DPE
    # rules take the worse (higher) of the two letters.
    return max(
        energy_class_from_consumption_score(energy_score),
        energy_class_from_ges_score(ges_score),
    )


def energy_class_from_consumption_score(score: int) -> str:
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


def energy_class_from_ges_score(score: int) -> str:
    if score <= 6:
        return "A"
    if score <= 11:
        return "B"
    if score <= 30:
        return "C"
    if score <= 50:
        return "D"
    if score <= 70:
        return "E"
    if score <= 100:
        return "F"
    return "G"


def parse_century_construction_year(section) -> int | None:
    for item in get_century_global_view_items(section):
        text = item.get_text(" ", strip=True)

        if "construction" not in text.lower():
            continue

        match = re.search(r"(\d{4})", text)

        if match:
            year = int(match.group(1))
            if 1700 <= year <= datetime.now().year + 1:
                return year

    return None


def parse_century_posted_at(section):
    # Century21 detail pages don't expose a publication date anywhere
    # (structured fields or free text) at the time this was written.
    return None


def parse_century_floor(section) -> FloorInfo:
    floor = None
    is_top_floor = None

    for item in get_century_global_view_items(section):
        text = item.get_text(" ", strip=True)

        if "tage" not in text.lower():
            continue

        info = parse_floor_info(text)
        floor = info.floor
        is_top_floor = info.is_top_floor

        if floor is None:
            # parse_floor_info expects the ordinal before "étage" (e.g. "9e
            # étage"), but Century's structured field is "Étage : 9 ème" /
            # "Étage : 1 er" (label first) so it needs its own extraction.
            match = re.search(r"(\d+)\s*(?:[eè]me|er)\b", text, flags=re.IGNORECASE)
            if match:
                floor = int(match.group(1))
            elif re.search(r"\bRDC\b|rez.de.chauss", text, flags=re.IGNORECASE):
                floor = 0

        break

    # Century's structured "Étage" field never states whether it's the top
    # floor (e.g. "Étage : 8 ème" for a building with 8 floors total) — that
    # only ever shows up as free text in the description ("au 8 et dernier
    # étage"), so it needs its own fallback lookup.
    if is_top_floor is None:
        description_section = section.select_one("section.c-the-property-detail-description")
        if description_section is not None:
            desc_info = parse_floor_info(description_section.get_text(" ", strip=True))
            is_top_floor = desc_info.is_top_floor
            if floor is None:
                floor = desc_info.floor

    return FloorInfo(floor=floor, is_top_floor=is_top_floor)


class CenturySource(RentalListingSource):
    name = "century"
    search_url = "https://www.century21.fr/annonces/f/location-appartement/v-issy+les+moulineaux-paris-st+cyr+l+ecole-velizy+villacoublay/s-25-/st-0-/b-0-1200/"
    storage_path = "data/raw/century_htmls"
    detail_storage_path = "data/raw/century_details_htmls"
    parser = staticmethod(parse_century_search_html)

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
            file_path = folder / f"century_playwright_{i + 1}.html"
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
        soup = BeautifulSoup(html, "html.parser")

        # Unlike Bienici, a Century21 detail page is dedicated to a single
        # listing (no ajax-loaded sibling sheets sharing the DOM), so there's
        # no need to scope to a per-listing section id before parsing.
        if soup.select_one(".c-the-property-detail-global-view__list") is None:
            logger.warning(f"Detail content not found for century listing {listing.source_id}")
            listing.details_fetched_at = datetime.now(UTC)
            return

        listing.energy_class = parse_century_energy_class(section=soup)
        listing.construction_year = parse_century_construction_year(section=soup)
        listing.posted_at = parse_century_posted_at(section=soup)
        floor_info = parse_century_floor(section=soup)
        listing.floor = floor_info.floor
        listing.is_top_floor = floor_info.is_top_floor

        # The search-card description is truncated, so the full detail-page
        # description can reveal a "vue dégagée" that was cut off earlier;
        # only upgrade to True, never overwrite a True found on the card.
        description_section = soup.select_one("section.c-the-property-detail-description")
        if description_section is not None and has_clear_view(
            description_section.get_text(" ", strip=True)
        ):
            listing.clear_view = True
        listing.details_fetched_at = datetime.now(UTC)
        print(f"url: {listing.url}, posted date: {listing.posted_at}")


def parse_century_sale_search_html(html: str) -> list[RentalListing]:
    return parse_century_search_html(html, source="century_sale", is_rental=False)


class CenturySaleSource(CenturySource):
    name = "century_sale"
    search_url = (
        "https://www.century21.fr/annonces/f/achat-appartement/v-paris/s-50-/st-0-/b-0-650000/p-3/"
    )
    storage_path = "data/raw/century_sale_htmls"
    detail_storage_path = "data/raw/century_sale_details_htmls"
    parser = staticmethod(parse_century_sale_search_html)
