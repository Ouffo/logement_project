from bs4 import BeautifulSoup

from src.ingestion.http_client import fetch_html
from src.utils.logger import logger


def fetch_page_title(url: str) -> str:
    html = fetch_html(url)

    soup = BeautifulSoup(html, "html.parser")

    title = soup.select_one("title")

    if title is None:
        logger.warning(f"No title found for url={url}")
        return ""

    return title.get_text(strip=True)


if __name__ == "__main__":
    title = fetch_page_title("https://example.com")
    logger.info(title)