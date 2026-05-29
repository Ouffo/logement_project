# scripts/test_leboncoin_combined_html.py

from src.ingestion.browser_client import (
    browser_context,
    open_page,
    get_rendered_html,
    close_page,
)
from src.ingestion.sources.leboncoin_source import (
    LEBONCOIN_URL,
    collect_leboncoin_listing_urls,
)
from src.utils.scrapping import save_combined_html
from src.utils.logger import logger


with browser_context(headless=False) as context:
    search_page = open_page(context, LEBONCOIN_URL)

    urls = collect_leboncoin_listing_urls(search_page)
    search_page.wait_for_timeout(2000)  # Wait for 2 seconds to ensure all content is loaded
    close_page(search_page)

    logger.info(f"Found {len(urls)} urls")

    html_pages = []

    for url in urls:
        logger.info(f"Fetching detail page: {url}")

        page = open_page(context, url)
        html = get_rendered_html(page)
        close_page(page)

        html_pages.append((url, html))

    save_combined_html(
        html_pages,
        "data/raw/leboncoin/details_combined.html",
    )

    logger.info("Saved combined HTML")