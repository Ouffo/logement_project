from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.sources.seloger_source import (
    clean_text,
    clean_url,
    parse_available_at,
    parse_district_name,
    parse_postal_code,
    parse_price_eur,
    parse_rooms,
    parse_seloger_card,
    parse_seloger_search_html,
    parse_seloger_source_id,
    parse_surface_m2,
    parse_title,
    with_page_param,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_parse_price_eur_none_input():
    assert parse_price_eur(None) is None


def test_parse_price_eur_no_match():
    assert parse_price_eur("pas de prix ici") is None


def test_parse_price_eur_simple():
    assert parse_price_eur("900 €") == 900


def test_parse_price_eur_with_nbsp_separators():
    # Seloger renders prices with a narrow no-break space (U+202F) between
    # thousands and a regular no-break space (U+00A0) before the currency sign
    price_str = "1" + chr(0x202F) + "178" + chr(0xA0) + "€ /mois"
    assert parse_price_eur(price_str) == 1178


def test_clean_text_collapses_whitespace_and_nbsp():
    text = "  Bel   appartement      "
    assert clean_text(text) == "Bel appartement"


def test_clean_text_none_input():
    assert clean_text(None) is None


def test_clean_text_blank_input_returns_none():
    assert clean_text("   ") is None


def test_clean_url_makes_relative_url_absolute():
    url = clean_url("/annonces/locations/appartement-123456.htm?utm_source=x")
    assert url == "https://www.seloger.com/annonces/locations/appartement-123456.htm"


def test_clean_url_strips_query_and_fragment():
    url = clean_url("https://www.seloger.com/annonces/locations/appartement-123456.htm#section")
    assert url == "https://www.seloger.com/annonces/locations/appartement-123456.htm"


def test_clean_url_none_input():
    assert clean_url(None) is None


def test_parse_seloger_source_id_from_url():
    url = "https://www.seloger.com/annonces/locations/appartement/paris-10eme-75/x/273902837.htm"
    assert parse_seloger_source_id(url) == "273902837"


def test_parse_seloger_source_id_url_without_numeric_segment():
    assert parse_seloger_source_id("https://www.seloger.com/no-id-here.htm") is None


def test_parse_seloger_source_id_falls_back_to_card_id():
    assert parse_seloger_source_id(None, "classified-card-987654") == "987654"


def test_parse_seloger_source_id_no_url_or_card_id():
    assert parse_seloger_source_id(None, None) is None


def test_parse_surface_m2():
    assert parse_surface_m2("2 pièces 30 m² 3ème étage") == 30.0


def test_parse_surface_m2_none_input():
    assert parse_surface_m2(None) is None


def test_parse_surface_m2_no_match():
    assert parse_surface_m2("rien") is None


def test_parse_rooms():
    assert parse_rooms("2 pièces 30 m²") == 2


def test_parse_rooms_none_input():
    assert parse_rooms(None) is None


def test_parse_rooms_no_match():
    assert parse_rooms("rien") is None


def test_parse_available_at():
    assert parse_available_at("Libre dès le 15/08/2026") == datetime(2026, 8, 15, tzinfo=UTC)


def test_parse_available_at_none_input():
    assert parse_available_at(None) is None


def test_parse_available_at_no_match():
    assert parse_available_at("rien") is None


def test_parse_postal_code():
    assert parse_postal_code("Paris 17ème arrondissement (75017)") == "75017"


def test_parse_postal_code_none_input():
    assert parse_postal_code(None) is None


def test_parse_postal_code_no_match():
    assert parse_postal_code("rien") is None


def test_parse_district_name():
    text = "Champerret-Berthier, Paris 17ème arrondissement (75017)"
    assert parse_district_name(text) == "Champerret-Berthier"


def test_parse_district_name_none_input():
    assert parse_district_name(None) is None


def test_parse_district_name_no_match():
    assert parse_district_name("rien") is None


def test_parse_title_matches_known_property_types():
    assert parse_title("Appartement à louer Champerret-Berthier") == "Appartement à louer"
    assert parse_title("Studio à louer proche métro") == "Studio à louer"


def _card(html: str):
    return BeautifulSoup(html, "html.parser").select_one(
        '[data-testid="serp-core-classified-card-testid"]'
    )


def test_parse_seloger_card_skips_zero_surface():
    html = """
    <div data-testid="serp-core-classified-card-testid" id="classified-card-999">
      <a data-testid="card-mfe-covering-link-testid"
         href="https://www.seloger.com/annonces/locations/appartement/paris-11eme-75/x/999.htm"></a>
      <div data-testid="cardmfe-price-testid">900 €</div>
      <div data-testid="cardmfe-keyfacts-testid">0 m² · 2 pièces</div>
      <div data-testid="cardmfe-description-box-text-test-id">Appartement à louer</div>
    </div>
    """
    assert parse_seloger_card(_card(html)) is None


def test_parse_seloger_card_skips_zero_price():
    html = """
    <div data-testid="serp-core-classified-card-testid" id="classified-card-998">
      <a data-testid="card-mfe-covering-link-testid"
         href="https://www.seloger.com/annonces/locations/appartement/paris-11eme-75/x/998.htm"></a>
      <div data-testid="cardmfe-price-testid">0 €</div>
      <div data-testid="cardmfe-keyfacts-testid">45 m² · 2 pièces</div>
      <div data-testid="cardmfe-description-box-text-test-id">Appartement à louer</div>
    </div>
    """
    assert parse_seloger_card(_card(html)) is None


def test_parse_title_matches_sale_listings():
    assert parse_title("Appartement à vendre Champerret-Berthier") == "Appartement à vendre"
    assert parse_title("Studio à vendre proche métro") == "Studio à vendre"


def test_parse_title_no_match():
    assert parse_title("Maison individuelle avec jardin") is None


def test_parse_title_none_input():
    assert parse_title(None) is None


def test_with_page_param_adds_page_query_param():
    url = with_page_param("https://www.seloger.com/search?foo=bar", 3)
    assert url == "https://www.seloger.com/search?foo=bar&page=3"


def test_with_page_param_overrides_existing_page_param():
    url = with_page_param("https://www.seloger.com/search?page=1", 5)
    assert url == "https://www.seloger.com/search?page=5"


def test_parse_seloger_search_html_extracts_real_listings():
    # seloger_search_sample.html is a real (trimmed) capture of a
    # seloger.com search-results page, as saved by SeLogerSource.fetch_html
    # in production.
    html = _read_fixture("seloger_search_sample.html")

    listings = parse_seloger_search_html(html)

    assert len(listings) == 4
    assert all(listing.source == "seloger" for listing in listings)
    assert all(listing.price_eur > 0 for listing in listings)
    assert all(listing.surface_m2 > 0 for listing in listings)


def test_parse_seloger_search_html_specific_listing_fields():
    html = _read_fixture("seloger_search_sample.html")

    listings = {listing.source_id: listing for listing in parse_seloger_search_html(html)}

    listing = listings["272667477"]
    assert listing.price_eur == 1180
    assert listing.surface_m2 == 28.0
    assert listing.rooms == 1
    assert listing.postal_code == "75013"
    assert listing.energy_class == "C"
    assert listing.floor == 7
    assert listing.is_top_floor is None


def test_parse_seloger_search_html_detects_non_top_floor():
    html = _read_fixture("seloger_search_sample.html")

    listings = {listing.source_id: listing for listing in parse_seloger_search_html(html)}

    listing = listings["273449163"]
    assert listing.floor == 2
    assert listing.is_top_floor is False


def test_parse_seloger_search_html_deduplicates_by_source_id():
    html = _read_fixture("seloger_search_sample.html")

    listings = parse_seloger_search_html(html + html)

    assert len(listings) == 4
