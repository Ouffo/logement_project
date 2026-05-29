from bs4 import BeautifulSoup
import time
from src.ingestion.http_client import fetch_html
from src.utils.logger import logger


BASE_URL = (
    "https://books.toscrape.com/catalogue/"
)


def fetch_books_page(
    page_number: int,
) -> list[dict]:

    url = (
        BASE_URL +
        f"page-{page_number}.html"
    )

    html = fetch_html(url)

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    books = []

    for book_el in soup.select(
        ".product_pod"
    ):

        try:

            title = (
                book_el
                .select_one("h3 a")
                .get("title")
            )

            price = (
                book_el
                .select_one(".price_color")
                .get_text(strip=True)
            )

            availability = (
                book_el
                .select_one(".availability")
                .get_text(strip=True)
            )

            books.append(
                {
                    "title": title,
                    "price": price,
                    "availability": availability,
                }
            )

        except Exception:
            logger.exception(
                "Failed parsing book"
            )

    logger.info(
        f"Fetched page "
        f"{page_number} "
        f"with {len(books)} books"
    )

    return books


def fetch_all_books(
    max_pages: int = 3,
) -> list[dict]:

    all_books = []

    for page_number in range(
        1,
        max_pages + 1,
    ):

        books = fetch_books_page(
            page_number
        )

        all_books.extend(
            books
        )
        time.sleep(1)

    logger.info(
        f"Fetched total "
        f"{len(all_books)} books"
    )

    return all_books