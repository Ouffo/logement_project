import json
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

# The site never shows a postal code directly, only "Paris 13Eme" for Paris
# or the bare suburb name for everything else in our search scope.
SUBURB_NAME_TO_POSTAL_CODE = {
    r"V[ée]lizy-Villacoublay": "78140",
    r"Issy-les-Moulineaux": "92130",
    r"Saint-Cyr-l['’][eé]cole": "78210",
}

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
    # Real example: "Au sein d'un bel immeuble haussmannien de six étages
    # édifié en 1900, cet appartement ... au dernier étage avec ascenseur"
    # — the building's total floor count and the "dernier étage" confirmation
    # are in different clauses, so this is only useful combined with an
    # already-established is_top_floor=True.
    match = re.search(
        rf"immeuble[^.\n]{{0,40}}\bde\s+(\d+|{_CARDINAL_WORDS_PATTERN})\s+[eé]tages?\b",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = match.group(1).lower()
    return int(value) if value.isdigit() else CARDINAL_WORDS.get(value)


def parse_maison_et_appartement_floor_from_text(text: str | None) -> FloorInfo:
    if not text:
        return FloorInfo(floor=None, is_top_floor=None)

    # The description sometimes states "dernier étage" in one sentence and
    # the actual floor number in a later one (e.g. "APPARTEMENT ... DERNIER
    # ÉTAGE ... VUE DÉGAGÉE. Au cinquième étage et dernier étage, ..."), so
    # parse_floor_info's first-sentence-match can miss the number — merge
    # across all sentences instead of stopping at the first one.
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


def parse_maison_et_appartement_postal_code(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"paris\s*(\d{1,2})\s*(?:er|[eè]me)?\b", text, flags=re.IGNORECASE)
    if match:
        return f"75{int(match.group(1)):03d}"

    for pattern, postal_code in SUBURB_NAME_TO_POSTAL_CODE.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            return postal_code

    match = re.search(rf"\b({EXTRA_POSTAL_CODES_PATTERN})\b", text)
    return match.group(1) if match else None


def parse_maison_et_appartement_search_html(
    html: str,
    source: str = "maison_et_appartement",
    is_rental: bool = True,
) -> list[RentalListing]:
    soup = BeautifulSoup(html, "html.parser")

    listings = []
    seen_ids = set()

    for card in soup.select("article.blkresult[id]"):
        source_id = card.get("id")

        if not source_id or source_id in seen_ids:
            continue

        seen_ids.add(source_id)

        link_el = card.select_one("a.seeMore[href], a.cookieRoom[href]")
        if not link_el:
            logger.info(f"Skipping maison_et_appartement listing without url: {source_id}")
            continue

        url = link_el.get("href")

        image_el = card.select_one("img.diapo")
        image_url = (image_el.get("data-src") or image_el.get("src")) if image_el else None

        title_el = card.select_one(".RR_detail1")
        ville_el = card.select_one(".RR_ville_text")
        price_el = card.select_one(".RR_prix")
        description_el = card.select_one("[itemprop=description]")
        rooms_el = card.select_one("[itemprop=numberOfRooms]")
        surface_el = card.select_one("[itemprop=floorSize]")

        if not title_el or not price_el:
            logger.info(f"Skipping malformed maison_et_appartement listing: {source_id}")
            continue

        title = title_el.get_text(" ", strip=True)
        ville_text = ville_el.get_text(" ", strip=True) if ville_el else None
        description = description_el.get_text(" ", strip=True) if description_el else None

        price_eur = parse_price(price_el.get_text(" ", strip=True))
        surface_m2 = parse_surface(surface_el.get_text(" ", strip=True)) if surface_el else None
        rooms = int(rooms_el.get_text(strip=True)) if rooms_el else None

        if not surface_m2 or not price_eur:
            logger.info(
                f"Skipping maison_et_appartement listing without surface/price: {source_id}"
            )
            continue

        postal_code = parse_maison_et_appartement_postal_code(ville_text)
        city = city_from_postal_code(postal_code)

        full_text = f"{title}\n{description or ''}"
        floor_info = parse_maison_et_appartement_floor_from_text(full_text)

        listing = RentalListing(
            source=source,
            source_id=source_id,
            url=url,
            title=title,
            description=description,
            city=city,
            postal_code=postal_code,
            address=None,
            district_name=ville_text,
            price_eur=price_eur,
            surface_m2=surface_m2,
            rooms=rooms,
            bedrooms=None,
            is_rental=is_rental,
            floor=floor_info.floor,
            is_top_floor=floor_info.is_top_floor,
            furnished=("meublé" in full_text.lower() or "meublée" in full_text.lower()),
            parking="parking" in full_text.lower(),
            quiet=("calme" in full_text.lower() or "silencieux" in full_text.lower()),
            clear_view=has_clear_view(full_text),
            posted_at=None,
            image_url=image_url,
        )

        listings.append(listing)

    return listings


def get_maison_et_appartement_json_ld(soup, ld_type: str) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (ValueError, TypeError):
            continue
        if data.get("@type") == ld_type:
            return data
    return None


def parse_maison_et_appartement_energy_class(section) -> str | None:
    label = section.select_one("#dpe_etiquette")

    if label is None:
        return None

    for css_class in label.get("class", []):
        match = re.match(r"dpe2-([a-g])$", css_class, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None


def parse_maison_et_appartement_construction_year(section):
    # Not exposed anywhere (structured fields or free text) on this site's
    # detail pages at the time this was written.
    return None


def parse_maison_et_appartement_posted_at(section):
    # Not exposed anywhere on this site's detail pages at the time this was
    # written.
    return None


def parse_maison_et_appartement_floor(section) -> FloorInfo:
    # There's no structured "Étage" field at all on this site — the full,
    # untruncated description (from the JSON-LD Product block) is the only
    # source, unlike the search card's description which is cut short.
    product = get_maison_et_appartement_json_ld(section, "Product")
    description = product.get("description") if product else None

    return parse_maison_et_appartement_floor_from_text(description)


class MaisonEtAppartementSource(RentalListingSource):
    name = "maison_et_appartement"
    search_url = "https://www.maisonsetappartements.fr/views/Search.php?lang=fr&TypeAnnonce=LOC&TypeBien=APP&villes=34122,38338&departement=75&quartier=&bdgMin=&bdgMax=1200&surfMin=25&surfMax=&nb_piece=&nb_km=&keywords="
    storage_path = "data/raw/maison_et_appartement_htmls"
    detail_storage_path = "data/raw/maison_et_appartement_details_htmls"
    parser = staticmethod(parse_maison_et_appartement_search_html)

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
            file_path = folder / f"maison_et_appartement_playwright_{i + 1}.html"
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

                    # This site started serving empty shell pages after
                    # ~94 rapid, sequential detail-page fetches in one run
                    # (real listings, confirmed reachable individually with
                    # a fresh browser profile — almost certainly anti-bot
                    # rate limiting). Space requests out, with a longer
                    # break every 15 fetches, to look less bot-like.
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

        listing.energy_class = parse_maison_et_appartement_energy_class(section=soup)
        listing.construction_year = parse_maison_et_appartement_construction_year(section=soup)
        listing.posted_at = parse_maison_et_appartement_posted_at(section=soup)
        floor_info = parse_maison_et_appartement_floor(section=soup)
        listing.floor = floor_info.floor
        listing.is_top_floor = floor_info.is_top_floor

        # The search-card description is truncated twice over (once for
        # desktop, more for mobile); the JSON-LD Product block on the detail
        # page carries the full text, which can reveal a "vue dégagée" cut
        # off earlier — only upgrade to True, never overwrite a True found
        # on the card.
        product = get_maison_et_appartement_json_ld(soup, "Product")
        full_description = product.get("description") if product else None
        if full_description:
            if not listing.description or len(full_description) > len(listing.description):
                listing.description = full_description
            if has_clear_view(full_description):
                listing.clear_view = True

        listing.details_fetched_at = datetime.now(UTC)


def parse_maison_et_appartement_sale_search_html(html: str) -> list[RentalListing]:
    return parse_maison_et_appartement_search_html(
        html, source="maison_et_appartement_sale", is_rental=False
    )


class MaisonEtAppartementSaleSource(MaisonEtAppartementSource):
    name = "maison_et_appartement_sale"
    search_url = "https://www.maisonsetappartements.fr/views/Search.php?lang=fr&TypeAnnonce=VEN&TypeBien=APP&villes=&departement=75&quartier=&bdgMin=&bdgMax=650000&surfMin=50&surfMax=&nb_piece=3&nb_km=&keywords="
    storage_path = "data/raw/maison_et_appartement_sale_htmls"
    detail_storage_path = "data/raw/maison_et_appartement_sale_details_htmls"
    parser = staticmethod(parse_maison_et_appartement_sale_search_html)
