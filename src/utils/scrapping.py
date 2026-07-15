import random
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment

from src.utils.logger import logger

# Postal codes outside Paris (75xxx) that are in scope for the search.
POSTAL_CODE_TO_CITY = {
    "78140": "Vélizy-Villacoublay",
    "92130": "Issy-les-Moulineaux",
    "78210": "Saint-Cyr-l'École",
}

# Regex alternation for the postal codes above, for sources whose listing
# text only exposes "<city> <postal_code>" without a clean field split.
EXTRA_POSTAL_CODES_PATTERN = "|".join(re.escape(code) for code in POSTAL_CODE_TO_CITY)

# Regex alternation for the city names above, tolerant to straight/curly
# apostrophes and accent variants as they appear in scraped text.
EXTRA_CITY_NAMES_PATTERN = "|".join(
    [
        r"V[ée]lizy-Villacoublay",
        r"Issy-les-Moulineaux",
        r"Saint-Cyr-l['’][eé]cole",
    ]
)


def city_from_postal_code(postal_code: str | None) -> str:
    return POSTAL_CODE_TO_CITY.get(postal_code, "Paris")


FRENCH_ORDINAL_WORDS = {
    "premier": 1,
    "première": 1,
    "premiere": 1,
    "deuxième": 2,
    "deuxieme": 2,
    "troisième": 3,
    "troisieme": 3,
    "quatrième": 4,
    "quatrieme": 4,
    "cinquième": 5,
    "cinquieme": 5,
    "sixième": 6,
    "sixieme": 6,
    "septième": 7,
    "septieme": 7,
    "huitième": 8,
    "huitieme": 8,
    "neuvième": 9,
    "neuvieme": 9,
    "dixième": 10,
    "dixieme": 10,
    "onzième": 11,
    "onzieme": 11,
    "douzième": 12,
    "douzieme": 12,
    "treizième": 13,
    "treizieme": 13,
    "quatorzième": 14,
    "quatorzieme": 14,
    "quinzième": 15,
    "quinzieme": 15,
    "seizième": 16,
    "seizieme": 16,
    "dix-septième": 17,
    "dix-septieme": 17,
    "dix-huitième": 18,
    "dix-huitieme": 18,
    "dix-neuvième": 19,
    "dix-neuvieme": 19,
    "vingtième": 20,
    "vingtieme": 20,
}

_FRENCH_ORDINAL_WORDS_PATTERN = "|".join(FRENCH_ORDINAL_WORDS)


@dataclass
class FloorInfo:
    floor: int | None
    is_top_floor: bool | None


def _parse_floor_from_sentence(sentence: str) -> FloorInfo:
    if re.search(r"rez.de.chauss[ée]e|\bRDC\b", sentence, flags=re.IGNORECASE):
        return FloorInfo(floor=0, is_top_floor=None)

    floor: int | None = None
    is_top_floor: bool | None = None

    # "Dernier étage (sur N)" — definitively the top floor, N total floors.
    last_floor_match = re.search(
        r"dernier\s+[eé]tage\s*\(sur\s*(\d+)\)",
        sentence,
        flags=re.IGNORECASE,
    )
    if last_floor_match:
        floor = int(last_floor_match.group(1))
        is_top_floor = True

    # "Étage 4/6" (Seloger format: floor/total floors in the building). A
    # negative floor equal to minus the total (e.g. "-3/3") is a known
    # Seloger display quirk for the top floor, not a real basement level.
    if floor is None:
        ratio_match = re.search(r"[ée]tage\s+(-?\d+)\s*/\s*(\d+)", sentence, flags=re.IGNORECASE)
        if ratio_match:
            floor_value = int(ratio_match.group(1))
            total_floors = int(ratio_match.group(2))
            floor = total_floors if floor_value == -total_floors else floor_value
            is_top_floor = floor == total_floors

    # "2e étage", "1er étage (sur 3)" — ordinal directly followed by
    # "étage", with an optional "(sur M)" giving the building's total.
    if floor is None:
        match = re.search(
            r"(-?\d+)(?:ᵉʳ|ᵉ|er|ère|[eè]me|e)\s+[eé]tage(?:\s*\(sur\s*(\d+)\))?",
            sentence,
            flags=re.IGNORECASE,
        )
        if match:
            floor = int(match.group(1))
            total = match.group(2)
            if total:
                is_top_floor = floor == int(total)

    # "au 4ème et dernier étage", "au 3e avec ascenseur" — looser match for
    # when "étage"/"ascenseur" isn't directly adjacent, gated on the "au"
    # prefix: real listings phrase the floor as "au <ordinal>", whereas
    # arrondissement mentions ("dans le 18e") don't use "au" this way.
    if floor is None:
        match = re.search(
            r"\bau\s+(-?\d+)(?:ᵉʳ|ᵉ|er|ère|[eè]me|e)\b(?=.*(?:[eé]tage|ascenseur))",
            sentence,
            flags=re.IGNORECASE,
        )
        if match:
            floor = int(match.group(1))

    # "au deuxième étage" — spelled-out ordinals, only next to "étage"
    # since these words aren't used for arrondissements.
    if floor is None:
        word_match = re.search(
            rf"\b({_FRENCH_ORDINAL_WORDS_PATTERN})\b\s+[eé]tage",
            sentence,
            flags=re.IGNORECASE,
        )
        if word_match:
            floor = FRENCH_ORDINAL_WORDS[word_match.group(1).lower()]

    # "au 2 étage" — informal writing that drops the ordinal suffix
    # entirely. Requires "au" + singular "étage" right after the number
    # (not "étages", which is the building's total floor count), so it
    # doesn't collide with dates like "au 15 juillet".
    if floor is None:
        bare_match = re.search(r"\bau\s+(-?\d+)\s+[eé]tage\b", sentence, flags=re.IGNORECASE)
        if bare_match:
            floor = int(bare_match.group(1))

    # "au dernier étage" without a disclosed total — no absolute floor
    # number, but we still know it's the top one.
    if is_top_floor is None and re.search(r"dernier\s+[eé]tage", sentence, flags=re.IGNORECASE):
        is_top_floor = True

    if floor is None and is_top_floor is None:
        return FloorInfo(floor=None, is_top_floor=None)

    return FloorInfo(floor=floor, is_top_floor=is_top_floor)


def parse_floor_info(text: str | None) -> FloorInfo:
    if not text:
        return FloorInfo(floor=None, is_top_floor=None)

    for sentence in re.split(r"[.\n]", text):
        info = _parse_floor_from_sentence(sentence)
        if info.floor is not None or info.is_top_floor is not None:
            return info

    return FloorInfo(floor=None, is_top_floor=None)


def parse_floor(text: str | None) -> int | None:
    return parse_floor_info(text).floor


def dismiss_cookie_banner(page):
    page.wait_for_timeout(2000)  # Wait for 2 seconds to ensure the cookie banner is loaded
    # cookie_btn = (
    #     page.get_by_role("button", name="Continuer sans accepter")
    #     .or_(page.get_by_role("button", name="Tout refuser"))
    #     .or_(page.get_by_role("button", name="Refuser"))
    #     .or_(page.get_by_role("button", name="Je refuse"))
    #     .or_(page.get_by_role("button", name="Decline"))
    # )
    cookie_btn = page.locator(
        "button:has-text('Continuer sans accepter'), "
        "a:has-text('Continuer sans accepter'), "
        "button:has-text('Tout refuser'), "
        "a:has-text('Tout refuser')"
    )

    if cookie_btn.count() > 0:
        logger.info("Found cookie button")
        cookie_btn.first.click()


def simulate_scroll(page):
    while True:
        scroll_y = page.evaluate("window.scrollY")
        max_scroll = page.evaluate("document.body.scrollHeight - window.innerHeight")

        if scroll_y >= max_scroll:
            logger.info("Reached the bottom of the page")
            break

        page.mouse.wheel(
            0,
            random.randint(1200, 2000),
        )

        page.wait_for_timeout(random.randint(1500, 4000))


def get_next_page_url(page) -> str | None:
    patterns = [
        page.locator("a[rel='next']"),
        page.get_by_role("link", name="Suivant"),
        page.get_by_role("link", name="Next"),
        page.get_by_role("button", name="Page suivante"),
        page.locator(".pagination-next a"),
        page.locator("[aria-label='Page suivante']"),
    ]
    for locator in patterns:
        if locator.count() > 0:
            logger.info("Found next page button")
            base_url = page.url  # URL actuelle de la page
            href = locator.first.get_attribute("href")
            if href:
                full_url = urljoin(base_url, href)
                logger.info(f"Next page URL: {full_url}")
                return full_url
            else:
                logger.info("found locator to click")
    return None  # Pas de page suivante


REMOVE_TAGS = {
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "canvas",
    "footer",
    "nav",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "header",
}


REMOVE_SELECTORS = [
    '[id*="cookie"]',
    '[class*="cookie"]',
    '[id*="consent"]',
    '[class*="consent"]',
    '[class*="cmp"]',
    '[class*="banner"]',
    '[id*="dialog"]',
    '[class*="dialog"]',
    '[id*="modal"]',
    '[class*="modal"]',
    '[id*="popup"]',
    '[class*="popup"]',
    '[href*="signaler"]',
    '[href*="favoris"]',
    '[href*="envoi_ami"]',
]

REMOVE_TEXT_PATTERNS = [
    "Le bailleur a été notifié",
    "Ajouter à mes favoris",
    "Imprimer",
    "Les informations sur les risques",
    "NB : Le propriétaire refuse le démarchage commercial",
]

KEEP_ATTRS = {"href", "src", "alt", "class"}


def extract_body_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for selector in REMOVE_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    body = soup.body or soup

    main = body.find("main") or body.find("article") or body

    for pattern in REMOVE_TEXT_PATTERNS:
        for text_node in main.find_all(string=True):
            if pattern not in text_node:
                continue

            parent = text_node.parent
            if parent and parent.name in {"p", "a", "li", "span", "strong"}:
                parent.decompose()

    # Supprime commentaires HTML
    for comment in main.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Déduplique les images
    seen_img_srcs = set()
    for img in main.find_all("img"):
        src = img.get("src")
        if not src:
            img.decompose()
            continue

        if src in seen_img_srcs:
            img.decompose()
            continue

        seen_img_srcs.add(src)

    # Nettoie les liens vides
    for a in main.find_all("a"):
        href = a.get("href")
        text = a.get_text(strip=True)

        if not href and not text and not a.find("img"):
            a.decompose()

    # Supprime les div/span vides
    for tag in reversed(main.find_all(["div", "span", "p", "li", "ul"])):
        if not tag.get_text(strip=True) and not tag.find("img"):
            tag.decompose()

    # Garde seulement quelques attributs utiles
    for tag in main.find_all(True):
        tag.attrs = {key: value for key, value in tag.attrs.items() if key in KEEP_ATTRS}

    return main.decode_contents()


def extract_leboncoin_search_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    articles = soup.select("article")

    parts = ["<div class='leboncoin-search-results'>"]

    for article in articles:
        if article.select_one("a[href*='/ad/locations/']"):
            parts.append(str(article))

    parts.append("</div>")

    return "\n".join(parts)


def combine_htmls(
    html_pages: list[tuple[str, str]],
    section_class: str,
) -> str:
    parts = [
        "<html>",
        "<body>",
    ]

    for url, html in html_pages:
        parts.append(f'<section class="{section_class}" data-url="{url}">')
        parts.append(html)
        parts.append("</section>")

    parts.extend(
        [
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(parts)
