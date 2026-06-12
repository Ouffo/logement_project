# scripts/test_leboncoin_combined_html.py
import random

from pathlib import Path
from src.ingestion.browser_client import (
    browser_context,
    open_page,
    get_rendered_html,
    close_page,
)
from src.ingestion.sources.leboncoin_source import parse_leboncoin_search_html
from src.utils.scrapping import get_next_page_url
from src.utils.logger import logger


html_pages = []
search_url = "https://www.leboncoin.fr/recherche?category=8&locations=Paris__48.86017419624389_2.337177366534126_9370&price=800-1200"
html_pages = []
all_listings = []

with browser_context() as context:
    search_page = open_page(context, search_url)
    next_page = get_next_page_url(search_page)
    html_pages.append(get_rendered_html(search_page))
    while next_page:
        logger.info(f"Navigating to next page: {next_page}")
        search_page.goto(next_page, wait_until="domcontentloaded", timeout=60000)
        search_page.wait_for_timeout(random.choice([2000, 5000]))  # Random wait to mimic human behavior

        html_pages.append(get_rendered_html(search_page))
        next_page = get_next_page_url(search_page)
    close_page(search_page)

output_dir = Path("data/raw/leboncoin_htmls")
output_dir.mkdir(parents=True, exist_ok=True)

for i, html in enumerate(html_pages):            
    with open(output_dir / f"leboncoin_playwright_{i+1}.html", "w", encoding="utf-8") as file:
        file.write(html)
    
    all_listings.extend(parse_leboncoin_search_html(html))

logger.info(f"Total listings found: {len(all_listings)}")

for listing in all_listings[:5]:  # Print the first 5 listings for verification
    logger.info(f"Title: {listing.title}, Price: {listing.price_eur}, Location: {listing.postal_code}, URL: {listing.url}")    