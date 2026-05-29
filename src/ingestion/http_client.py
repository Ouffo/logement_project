import requests
import time
from src.utils.logger import logger

def fetch_json(url: str) -> dict:
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                     "Mozilla/5.0"
                )
            },
        )

        response.raise_for_status()
          # Raise an error for bad status codes
        return response.json()
    
    except requests.RequestException as e:
        logger.error(f"Error fetching data from {url}: {e}")
        return None
    
DEFAULT_HEADERS = {
    "User-Agent": "...",
    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": (
        "fr-FR,fr;q=0.9,en;q=0.8"
    ),
    "Referer": "https://google.com",
}

def fetch_html(
    url: str,
    max_retries: int = 3,
    delay_seconds: float = 1.0,
) -> str:
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url,
                timeout=15,
                headers=DEFAULT_HEADERS,
            )

            response.raise_for_status()

            return response.text

        except requests.HTTPError as e:
            status_code = e.response.status_code

            logger.warning(
                f"HTTP error {status_code} for url={url} "
                f"attempt={attempt}/{max_retries}"
            )

            if status_code in {403, 404}:
                raise

        except requests.RequestException as e:
            logger.warning(
                f"Request failed for url={url} "
                f"attempt={attempt}/{max_retries}: {e}"
            )

        if attempt < max_retries:
            time.sleep(delay_seconds * attempt)

    raise RuntimeError(f"Failed to fetch url={url}")