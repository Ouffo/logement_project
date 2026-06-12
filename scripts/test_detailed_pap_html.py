

from src.ingestion.browser_client import browser_context, close_page, get_rendered_html, open_page
from src.utils.scrapping import extract_body_content, simulate_scroll
from src.utils.scrapping import combine_htmls
from src.ingestion.sources.pap_source import parse_pap_html

def test_detailed_pap_html():
    html_pages = []
    search_url = "https://www.pap.fr/annonce/locations-appartement-paris-75-g439-du-studio-au-2-pieces-a-partir-de-1-chambres-jusqu-a-1200-euros-a-partir-de-25-m2"

    with browser_context() as context:
        search_page = open_page(context, search_url)
        simulate_scroll(search_page)
        html = get_rendered_html(search_page)
        close_page(search_page)

        listings = parse_pap_html(html)
        for listing in listings:
            page = open_page(context, str(listing.url))
            page.wait_for_timeout(1000)
            raw_html = get_rendered_html(page)
            cleaned_html = extract_body_content(raw_html)
            html_pages.append((str(listing.url), cleaned_html))
            close_page(page)

    combined_html = combine_htmls(html_pages)

    with open(f"data/raw/test_pap_detailed.html", "w", encoding="utf-8") as file:
        file.write(combined_html)

if __name__ == "__main__":
    test_detailed_pap_html()