from playwright.sync_api import sync_playwright
from src.ingestion.sources.base import Source
from src.utils.scrapping import (dismiss_cookie_banner, simulate_scroll, get_next_page_url)
from src.utils.logger import logger

def scrap_page(source: Source, page, html_list):
    page.wait_for_timeout(2000)

    if source.name == "leboncoin":
        cards = page.locator("a[href*='/ad/locations/']")
        seen = set()

        for i in range(cards.count()):
            card = cards.nth(i)
            href = card.get_attribute("href")

            if not href or href in seen:
                continue

            seen.add(href)

            logger.info("-" * 50)
            logger.info(href)

    else:
        logger.info("Simulating scroll to load dynamic content")
        simulate_scroll(page)

        logger.info("Saving page content")
        html_list.append(page.content())

def fetch_rendered_html(url: str, headless: bool = False) -> list[str]:
    html_list = []
    with sync_playwright() as p:
        
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./pap_profile",
            headless=headless,
            viewport={"width": 1200, "height": 800},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page = browser.new_page()

        logger.info(f"Navigating to {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        logger.info("Page loaded")

        #click on the cookie banner if it exists
        dismiss_cookie_banner(page)
        #next_page = get_next_page_url(page)
        next_page = None

        scrap_page(page, html_list)

        while next_page:
            logger.info(f"Navigating to next page: {next_page}")
            page.goto(next_page, wait_until="domcontentloaded", timeout=60000)
            logger.info("Page loaded")
            next_page = get_next_page_url(page)
            scrap_page(page, html_list)

        browser.close()

        return html_list


from contextlib import contextmanager
from playwright.sync_api import sync_playwright, BrowserContext, Page


@contextmanager
def browser_context(headless: bool = False):
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="./ouffo_profile",
            headless=headless,
            viewport={"width": 1200, "height": 800},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            args=["--disable-blink-features=AutomationControlled"],
        )

        try:
            yield context
        finally:
            context.close()


def open_page(
    context: BrowserContext,
    url: str,
    timeout: int = 60000,
) -> Page:
    page = context.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    dismiss_cookie_banner(page)
    return page


def get_rendered_html(page: Page) -> str:
    return page.content()


def close_page(page: Page) -> None:
    page.close()