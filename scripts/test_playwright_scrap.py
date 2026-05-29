from src.ingestion.browser_client import fetch_rendered_html
from src.utils.logger import logger

urls = {
   "pap":"https://www.pap.fr/annonce/locations-appartement-paris-75-g439-du-studio-au-2-pieces-a-partir-de-1-chambres-jusqu-a-1200-euros-a-partir-de-25-m2",
   "leboncoin" : "https://www.leboncoin.fr/recherche?category=8&locations=Paris__48.86017419624389_2.337177366534126_9370&price=800-1200"
}

files = {
   "pap":"data/raw/pap_playwright",
   "leboncoin":"data/raw/leboncoin_playwright"
}

html_list = fetch_rendered_html(urls["leboncoin"], headless=False)

for i, html in enumerate(html_list):
   logger.info(f"Saving HTML content of page {i+1}")
   with open(files["leboncoin"] + f"_{i+1}.html", "w", encoding="utf-8") as file:
      file.write(html)
