import random
from pathlib import Path

from bs4 import BeautifulSoup, Comment
from src.utils.logger import logger
from urllib.parse import urljoin

def dismiss_cookie_banner(page):
    page.wait_for_timeout(2000)  # Wait for 2 seconds to ensure the cookie banner is loaded
    cookie_btn = (
        page.get_by_role("button", name="Continuer sans accepter")
        .or_(page.get_by_role("button", name="Tout refuser"))
        .or_(page.get_by_role("button", name="Refuser"))
        .or_(page.get_by_role("button", name="Je refuse"))
        .or_(page.get_by_role("button", name="Decline"))
    )
    if cookie_btn.count() > 0:
        logger.info("Found cookie button")
        cookie_btn.first.click()

def simulate_scroll(page):
    while True:
        scroll_y = page.evaluate("window.scrollY")
        max_scroll = page.evaluate(
            "document.body.scrollHeight - window.innerHeight"
        )

        if scroll_y >= max_scroll:
            logger.info("Reached the bottom of the page")
            break

        page.mouse.wheel(
            0,
            random.randint(1200, 2000),
        )

        page.wait_for_timeout(
            random.randint(1500, 4000)
        )

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
    "header"
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

    main = (
        body.find("main")
        or body.find("article")
        or body
    )

    for pattern in REMOVE_TEXT_PATTERNS:
        for text_node in main.find_all(string=lambda text: text and pattern in text):
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
        tag.attrs = {
            key: value
            for key, value in tag.attrs.items()
            if key in KEEP_ATTRS
        }

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
