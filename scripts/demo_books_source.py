from src.ingestion.sources.books_demo_source import fetch_all_books
from src.utils.logger import logger

books = fetch_all_books()

logger.info(
    f"Total books: {len(books)}"
)

for book in books[:5]:
    logger.info(book)