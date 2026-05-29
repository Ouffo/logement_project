from src.ingestion.http_client import (
    fetch_html,
)


url = (
    "https://www.pap.fr/"
)

html = fetch_html(url)

with open(
    "data/raw/pap_homepage.html",
    "w",
    encoding="utf-8",
) as file:

    file.write(html)

print(
    "Saved HTML to "
    "data/raw/pap_homepage.html"
)