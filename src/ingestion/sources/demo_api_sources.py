from src.ingestion.http_client import fetch_json
from src.utils.logger import logger

def fetch_demo_api_data() -> dict:
    url = "https://jsonplaceholder.typicode.com/posts"
    data = fetch_json(url)
    if data is not None:
        logger.info(f"Fetched {len(data)} items from the demo API.")
    return data

if __name__ == "__main__":
    demo_data = fetch_demo_api_data()
    logger.info(demo_data)  # Print the first 2 items for verification