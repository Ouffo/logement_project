from bs4 import BeautifulSoup

from src.ingestion.http_client import (fetch_html)
from src.utils.logger import logger

url = "https://example.com"

html = fetch_html(url)

soup = BeautifulSoup(
    html,
    "html.parser",
)

logger.info(
    soup.prettify()[:2000]
)