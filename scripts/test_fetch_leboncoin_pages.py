import random
from src.ingestion.browser_client import browser_context, get_rendered_html, open_page, close_page
from src.processing.filters import is_valid_listing
from src.utils.scrapping import combine_htmls, extract_body_content
search_url = "https://www.leboncoin.fr/recherche?category=8&locations=Paris__48.86017419624389_2.337177366534126_9370&price=800-1200"
from src.ingestion.sources.leboncoin_source import get_next_page_url, parse_leboncoin_search_html
from src.utils.logger import logger

def analyse_leboncoin_page(page):
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


def test_fetch_leboncoin_pages():
    html_pages = []
    listing_htmls = []
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

        all_listings = []
        for i, html in enumerate(html_pages):
            logger.info(f"Processing page {i+1}")
            with open(f"data/raw/leboncoin_page_{i+1}.html", "w", encoding="utf-8") as file:
                file.write(html)
            listings = parse_leboncoin_search_html(html)
            all_listings.extend(listings)

            for listing in listings:
                logger.info(f"price:{listing.price_eur}, surface:{listing.surface_m2}, rooms:{listing.rooms}, url:{listing.url}")

        valid_listings = [
            listing 
            for listing in all_listings 
            if is_valid_listing(listing)
        ]
        
        logger.info(f"Total listings found: {len(all_listings)}")
        logger.info(f"Valid listings found: {len(valid_listings)}")

        for l in valid_listings[:5]:  # Log details of the first 5 valid listings
            logger.info(f"Valid listing - price: {l.price_eur}, surface: {l.surface_m2}, rooms: {l.rooms}, url: {l.url}, image_url: {l.image_url}")

if __name__ == "__main__":
    test_fetch_leboncoin_pages()
