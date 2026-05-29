from bs4 import BeautifulSoup

from src.ingestion.http_client import fetch_html
from src.utils.logger import logger

from bs4 import BeautifulSoup

from src.ingestion.http_client import fetch_html


url = "https://books.toscrape.com/"

html = fetch_html(url)
soup = BeautifulSoup(html, "html.parser")

for book in soup.select(".product_pod"):
    title = book.select_one("h3 a").get("title")
    price = book.select_one(".price_color").get_text(strip=True)
    availability = book.select_one(".availability").get_text(strip=True)

    logger.info("-" * 40)
    logger.info(f"Title: {title}")
    logger.info(f"Price: {price}")
    logger.info(f"Availability: {availability}")