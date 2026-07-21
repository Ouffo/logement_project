from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.sources.espaces_atypiques_source import (
    infer_floor_from_building_height,
    parse_espaces_atypiques_bedrooms,
    parse_espaces_atypiques_construction_year,
    parse_espaces_atypiques_energy_class,
    parse_espaces_atypiques_floor,
    parse_espaces_atypiques_floor_from_text,
    parse_espaces_atypiques_postal_code,
    parse_espaces_atypiques_posted_at,
    parse_espaces_atypiques_rooms,
    parse_espaces_atypiques_sale_search_html,
    parse_espaces_atypiques_search_html,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _real_detail_section():
    html = _read_fixture("espaces_atypiques_detail_sample.html")
    return BeautifulSoup(html, "html.parser")


def test_parse_espaces_atypiques_search_html_extracts_real_listings():
    # espaces_atypiques_search_sample.html is a real capture (2 valid cards
    # + 1 "sous compromis" card with no price) of an espaces-atypiques.com
    # search-results page.
    html = _read_fixture("espaces_atypiques_search_sample.html")

    listings = parse_espaces_atypiques_search_html(html)

    assert len(listings) == 2
    assert all(listing.source == "espaces_atypiques" for listing in listings)
    assert all(listing.is_rental for listing in listings)
    assert all(listing.price_eur > 0 for listing in listings)
    assert all(listing.surface_m2 > 0 for listing in listings)


def test_parse_espaces_atypiques_search_html_specific_listing_fields():
    html = _read_fixture("espaces_atypiques_search_sample.html")

    listings = {listing.source_id: listing for listing in parse_espaces_atypiques_search_html(html)}

    listing = listings["1397483"]
    assert listing.price_eur == 580000
    assert listing.surface_m2 == 50.5
    assert listing.postal_code == "75002"
    assert listing.city == "Paris"
    assert listing.image_url is not None
    assert str(listing.url) == (
        "https://www.espaces-atypiques.com/ventes/75002-paris-appartement-sur-cour-a-montorgueil-13962/"
    )


def test_parse_espaces_atypiques_search_html_skips_sous_compromis_without_price():
    # Real site behavior: a pending sale ("sous compromis") card has no
    # price span at all.
    html = _read_fixture("espaces_atypiques_search_sample.html")

    listings = parse_espaces_atypiques_search_html(html)

    assert "1252888" not in {listing.source_id for listing in listings}


def test_parse_espaces_atypiques_sale_search_html_forces_sale_fields():
    html = _read_fixture("espaces_atypiques_search_sample.html")

    listings = parse_espaces_atypiques_sale_search_html(html)

    assert len(listings) == 2
    assert all(listing.source == "espaces_atypiques_sale" for listing in listings)
    assert all(listing.is_rental is False for listing in listings)


def test_parse_espaces_atypiques_search_html_deduplicates_by_post_id():
    html = """
    <div class="preview-annonce">
        <div class="pictos"><div class="picto favori" data-post-id="dup1"></div></div>
        <a href="https://www.espaces-atypiques.com/ventes/x/"></a>
        <div class="infos">
            <div class="titre"><h2><a href="https://www.espaces-atypiques.com/ventes/x/">Appartement</a></h2></div>
            <span class="info localisation">
                <span class="ville">PARIS</span> <span>75011</span>
            </span>
            <span class="info font2">40 m²</span>
            <span class="info orange font2">300 000 €</span>
        </div>
    </div>
    <div class="preview-annonce">
        <div class="pictos"><div class="picto favori" data-post-id="dup1"></div></div>
        <a href="https://www.espaces-atypiques.com/ventes/x/"></a>
        <div class="infos">
            <div class="titre"><h2><a href="https://www.espaces-atypiques.com/ventes/x/">Appartement</a></h2></div>
            <span class="info localisation">
                <span class="ville">PARIS</span> <span>75011</span>
            </span>
            <span class="info font2">40 m²</span>
            <span class="info orange font2">300 000 €</span>
        </div>
    </div>
    """

    listings = parse_espaces_atypiques_search_html(html)

    assert len(listings) == 1


def test_parse_espaces_atypiques_search_html_skips_listing_without_post_id():
    html = """
    <div class="preview-annonce">
        <a href="https://www.espaces-atypiques.com/ventes/x/"></a>
        <div class="infos">
            <div class="titre"><h2><a href="https://www.espaces-atypiques.com/ventes/x/">Appartement</a></h2></div>
            <span class="info orange font2">300 000 €</span>
        </div>
    </div>
    """

    assert parse_espaces_atypiques_search_html(html) == []


def test_parse_espaces_atypiques_search_html_defaults_to_paris_without_parseable_city():
    html = """
    <div class="preview-annonce">
        <div class="pictos"><div class="picto favori" data-post-id="abc"></div></div>
        <a href="https://www.espaces-atypiques.com/ventes/x/"></a>
        <div class="infos">
            <div class="titre"><h2><a href="https://www.espaces-atypiques.com/ventes/x/">Appartement</a></h2></div>
            <span class="info localisation">Adresse non standard</span>
            <span class="info font2">40 m²</span>
            <span class="info orange font2">300 000 €</span>
        </div>
    </div>
    """

    listings = parse_espaces_atypiques_search_html(html)

    assert len(listings) == 1
    assert listings[0].city == "Paris"
    assert listings[0].postal_code is None


def test_parse_espaces_atypiques_postal_code():
    assert parse_espaces_atypiques_postal_code("PARIS 75002") == "75002"


def test_parse_espaces_atypiques_postal_code_extra_city():
    assert parse_espaces_atypiques_postal_code("ISSY-LES-MOULINEAUX 92130") == "92130"


def test_parse_espaces_atypiques_postal_code_no_match():
    assert parse_espaces_atypiques_postal_code("Adresse non standard") is None


def test_parse_espaces_atypiques_postal_code_none_input():
    assert parse_espaces_atypiques_postal_code(None) is None


def test_parse_espaces_atypiques_energy_class_from_real_section():
    # espaces_atypiques_detail_sample.html has li.classe-cep.active with
    # lettre-cep "C".
    assert parse_espaces_atypiques_energy_class(_real_detail_section()) == "C"


def test_parse_espaces_atypiques_energy_class_missing_label():
    section = BeautifulSoup("<div>Rien ici</div>", "html.parser")
    assert parse_espaces_atypiques_energy_class(section) is None


def test_parse_espaces_atypiques_rooms_from_real_section():
    assert parse_espaces_atypiques_rooms(_real_detail_section()) == 2


def test_parse_espaces_atypiques_bedrooms_from_real_section():
    assert parse_espaces_atypiques_bedrooms(_real_detail_section()) == 1


def test_parse_espaces_atypiques_rooms_no_match():
    html = '<div class="info-content"><ul><li>Charges annuelles : 100 €</li></ul></div>'
    section = BeautifulSoup(html, "html.parser")
    assert parse_espaces_atypiques_rooms(section) is None


def test_parse_espaces_atypiques_construction_year_always_none():
    assert parse_espaces_atypiques_construction_year(_real_detail_section()) is None


def test_parse_espaces_atypiques_posted_at_always_none():
    assert parse_espaces_atypiques_posted_at(_real_detail_section()) is None


def test_parse_espaces_atypiques_floor_from_real_section():
    # Real listing: "Étage : 6" and "6 étages dans l'immeuble" -> top floor.
    info = parse_espaces_atypiques_floor(_real_detail_section())
    assert info.floor == 6
    assert info.is_top_floor is True


def test_parse_espaces_atypiques_floor_not_top_floor():
    html = (
        '<div class="info-content"><ul>'
        "<li>Étage : 2</li><li>5 étages dans l'immeuble</li>"
        "</ul></div>"
    )
    section = BeautifulSoup(html, "html.parser")

    info = parse_espaces_atypiques_floor(section)
    assert info.floor == 2
    assert info.is_top_floor is False


def test_parse_espaces_atypiques_floor_without_total_floors():
    html = '<div class="info-content"><ul><li>Étage : 3</li></ul></div>'
    section = BeautifulSoup(html, "html.parser")

    info = parse_espaces_atypiques_floor(section)
    assert info.floor == 3
    assert info.is_top_floor is None


def test_parse_espaces_atypiques_floor_falls_back_to_description():
    html = """
    <div>
      <div class="info-content"><ul><li>2 pièces</li></ul></div>
      <div id="annonce-description"><p>Un appartement au dernier étage avec vue.</p></div>
    </div>
    """
    section = BeautifulSoup(html, "html.parser")

    info = parse_espaces_atypiques_floor(section)
    assert info.is_top_floor is True


def test_infer_floor_from_building_height_digit_form():
    assert infer_floor_from_building_height("immeuble de 8 étages") == 8


def test_infer_floor_from_building_height_word_form():
    assert infer_floor_from_building_height("immeuble haussmannien de six étages") == 6


def test_infer_floor_from_building_height_no_match():
    assert infer_floor_from_building_height("un bel appartement lumineux") is None


def test_parse_espaces_atypiques_floor_from_text_none_input():
    info = parse_espaces_atypiques_floor_from_text(None)
    assert info.floor is None
    assert info.is_top_floor is None
