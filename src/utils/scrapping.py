import random
from pathlib import Path
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

def combine_htmls(html_pages: list[tuple[str, str]]) -> str:
    parts = [
        "<html>",
        "<body>",
    ]

    for url, html in html_pages:
        parts.append(f'<section class="listing-detail" data-url="{url}">')
        parts.append(html)
        parts.append("</section>")

    parts.extend(
        [
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(parts)