from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.sources.maison_et_appartement_source import (
    get_maison_et_appartement_json_ld,
    infer_floor_from_building_height,
    parse_maison_et_appartement_construction_year,
    parse_maison_et_appartement_energy_class,
    parse_maison_et_appartement_floor,
    parse_maison_et_appartement_floor_from_text,
    parse_maison_et_appartement_postal_code,
    parse_maison_et_appartement_posted_at,
    parse_maison_et_appartement_sale_search_html,
    parse_maison_et_appartement_search_html,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _real_detail_section():
    html = _read_fixture("maison_et_appartement_detail_sample.html")
    return BeautifulSoup(html, "html.parser")


def test_parse_maison_et_appartement_search_html_extracts_real_listings():
    # maison_et_appartement_search_sample.html is a real (trimmed to 3
    # cards) capture of a maisonsetappartements.fr search-results page.
    html = _read_fixture("maison_et_appartement_search_sample.html")

    listings = parse_maison_et_appartement_search_html(html)

    assert len(listings) == 3
    assert all(listing.source == "maison_et_appartement" for listing in listings)
    assert all(listing.is_rental for listing in listings)
    assert all(listing.price_eur > 0 for listing in listings)
    assert all(listing.surface_m2 > 0 for listing in listings)


def test_parse_maison_et_appartement_search_html_specific_listing_fields():
    html = _read_fixture("maison_et_appartement_search_sample.html")

    listings = {
        listing.source_id: listing for listing in parse_maison_et_appartement_search_html(html)
    }

    listing = listings["4389031"]
    assert listing.price_eur == 350000
    assert listing.surface_m2 == 55.0
    assert listing.rooms == 3
    assert listing.postal_code == "75013"
    assert listing.city == "Paris"
    assert listing.image_url is not None
    assert "medias.maisonsetappartements.fr" in listing.image_url


def test_parse_maison_et_appartement_sale_search_html_forces_sale_fields():
    html = _read_fixture("maison_et_appartement_search_sample.html")

    listings = parse_maison_et_appartement_sale_search_html(html)

    assert len(listings) == 3
    assert all(listing.source == "maison_et_appartement_sale" for listing in listings)
    assert all(listing.is_rental is False for listing in listings)


def test_parse_maison_et_appartement_search_html_deduplicates_by_id():
    html = """
    <article class="blkresult" id="dup1">
        <a class="seeMore" href="https://www.maisonsetappartements.fr/x"></a>
        <span class="RR_detail1">Appartement à vendre</span>
        <span class="RR_ville_text">Paris 11Eme</span>
        <span class="RR_prix">300 000 €</span>
        <span itemprop="numberOfRooms">2</span>
        <span itemprop="floorSize">40</span>
    </article>
    <article class="blkresult" id="dup1">
        <a class="seeMore" href="https://www.maisonsetappartements.fr/x"></a>
        <span class="RR_detail1">Appartement à vendre</span>
        <span class="RR_ville_text">Paris 11Eme</span>
        <span class="RR_prix">300 000 €</span>
        <span itemprop="numberOfRooms">2</span>
        <span itemprop="floorSize">40</span>
    </article>
    """

    listings = parse_maison_et_appartement_search_html(html)

    assert len(listings) == 1


def test_parse_maison_et_appartement_search_html_skips_listing_without_surface():
    html = """
    <article class="blkresult" id="abc">
        <a class="seeMore" href="https://www.maisonsetappartements.fr/x"></a>
        <span class="RR_detail1">Appartement à vendre</span>
        <span class="RR_ville_text">Paris 11Eme</span>
        <span class="RR_prix">300 000 €</span>
    </article>
    """

    assert parse_maison_et_appartement_search_html(html) == []


def test_parse_maison_et_appartement_search_html_skips_non_numeric_price():
    # Regression: a real "programme neuf" (off-plan) listing rendered
    # "Immobilier neuf" instead of a price, which crashed parse_price with
    # an uncaught ValueError and took down the whole extract-save batch
    # instead of just skipping this one listing.
    html = """
    <article class="blkresult" id="abc">
        <a class="seeMore" href="https://www.maisonsetappartements.fr/x"></a>
        <span class="RR_detail1">Appartement à vendre</span>
        <span class="RR_ville_text">Paris 11Eme</span>
        <span class="RR_prix">Immobilier neuf</span>
        <span itemprop="numberOfRooms">2</span>
        <span itemprop="floorSize">40</span>
    </article>
    """

    assert parse_maison_et_appartement_search_html(html) == []


def test_parse_maison_et_appartement_search_html_skips_listing_without_link():
    html = """
    <article class="blkresult" id="abc">
        <span class="RR_detail1">Appartement à vendre</span>
        <span class="RR_ville_text">Paris 11Eme</span>
        <span class="RR_prix">300 000 €</span>
        <span itemprop="numberOfRooms">2</span>
        <span itemprop="floorSize">40</span>
    </article>
    """

    assert parse_maison_et_appartement_search_html(html) == []


def test_parse_maison_et_appartement_search_html_defaults_to_paris_without_parseable_city():
    html = """
    <article class="blkresult" id="abc">
        <a class="seeMore" href="https://www.maisonsetappartements.fr/x"></a>
        <span class="RR_detail1">Appartement à vendre</span>
        <span class="RR_ville_text">Adresse non standard</span>
        <span class="RR_prix">300 000 €</span>
        <span itemprop="numberOfRooms">2</span>
        <span itemprop="floorSize">40</span>
    </article>
    """

    listings = parse_maison_et_appartement_search_html(html)

    assert len(listings) == 1
    assert listings[0].city == "Paris"
    assert listings[0].postal_code is None


def test_parse_maison_et_appartement_search_html_prefers_data_src_over_placeholder_src():
    # Real site behavior: lazy-loaded images leave `src` pointing at a
    # generic placeholder while the real photo is only in `data-src`.
    html = """
    <article class="blkresult" id="abc">
        <a class="seeMore" href="https://www.maisonsetappartements.fr/x"></a>
        <img class="diapo" src="https://www.maisonsetappartements.fr/views/images/ext.jpg"
             data-src="https://medias.maisonsetappartements.fr/pict/real.jpg" />
        <span class="RR_detail1">Appartement à vendre</span>
        <span class="RR_ville_text">Paris 11Eme</span>
        <span class="RR_prix">300 000 €</span>
        <span itemprop="numberOfRooms">2</span>
        <span itemprop="floorSize">40</span>
    </article>
    """

    listings = parse_maison_et_appartement_search_html(html)

    assert listings[0].image_url == "https://medias.maisonsetappartements.fr/pict/real.jpg"


def test_parse_maison_et_appartement_postal_code_paris_arrondissement():
    assert parse_maison_et_appartement_postal_code("Paris 13Eme") == "75013"


def test_parse_maison_et_appartement_postal_code_paris_with_accent():
    assert parse_maison_et_appartement_postal_code("Paris 15ème") == "75015"


def test_parse_maison_et_appartement_postal_code_suburb_name():
    assert parse_maison_et_appartement_postal_code("Issy-les-Moulineaux") == "92130"


def test_parse_maison_et_appartement_postal_code_no_match():
    assert parse_maison_et_appartement_postal_code("Adresse non standard") is None


def test_parse_maison_et_appartement_postal_code_none_input():
    assert parse_maison_et_appartement_postal_code(None) is None


def test_get_maison_et_appartement_json_ld_finds_product():
    data = get_maison_et_appartement_json_ld(_real_detail_section(), "Product")
    assert data is not None
    assert data["@type"] == "Product"


def test_get_maison_et_appartement_json_ld_returns_none_for_missing_type():
    data = get_maison_et_appartement_json_ld(_real_detail_section(), "RealEstateAgent")
    assert data is None


def test_parse_maison_et_appartement_energy_class_from_real_section():
    # maison_et_appartement_detail_sample.html has id="dpe_etiquette" with
    # class "dpe2-g".
    assert parse_maison_et_appartement_energy_class(_real_detail_section()) == "G"


def test_parse_maison_et_appartement_energy_class_missing_label():
    section = BeautifulSoup("<div>Rien ici</div>", "html.parser")
    assert parse_maison_et_appartement_energy_class(section) is None


def test_parse_maison_et_appartement_construction_year_always_none():
    assert parse_maison_et_appartement_construction_year(_real_detail_section()) is None


def test_parse_maison_et_appartement_posted_at_always_none():
    assert parse_maison_et_appartement_posted_at(_real_detail_section()) is None


def test_parse_maison_et_appartement_floor_from_real_section():
    # The fixture's JSON-LD description reads "APPARTEMENT DE CHARME DERNIER
    # ÉTAGE AVEC ASCENSEUR. VUE DÉGAGÉE.\nAu cinquième étage et dernier
    # étage, ..." — the floor number only appears in the second sentence.
    info = parse_maison_et_appartement_floor(_real_detail_section())
    assert info.floor == 5
    assert info.is_top_floor is True


def test_parse_maison_et_appartement_floor_no_json_ld():
    section = BeautifulSoup("<div>Rien ici</div>", "html.parser")

    info = parse_maison_et_appartement_floor(section)
    assert info.floor is None
    assert info.is_top_floor is None


def test_parse_maison_et_appartement_floor_merges_across_sentences():
    html = """
    <script type="application/ld+json">
    {"@type": "Product",
     "description": "Bel appartement dernier étage. Au 3ème étage, vue sur jardin."}
    </script>
    """
    section = BeautifulSoup(html, "html.parser")

    info = parse_maison_et_appartement_floor(section)
    assert info.floor == 3
    assert info.is_top_floor is True


def test_infer_floor_from_building_height_real_example():
    # Real listing 4409945: the building's total floor count and the
    # "dernier étage" confirmation are in different clauses.
    text = (
        "Au sein d'un bel immeuble haussmannien de six étages édifié en 1900, "
        "cet appartement de 62,69m² au sol (59,17m² carrez), au dernier étage "
        "avec ascenseur, offre un potentiel certain."
    )
    assert infer_floor_from_building_height(text) == 6


def test_infer_floor_from_building_height_digit_form():
    assert infer_floor_from_building_height("immeuble de 8 étages") == 8


def test_infer_floor_from_building_height_no_match():
    assert infer_floor_from_building_height("un bel appartement lumineux") is None


def test_parse_maison_et_appartement_floor_from_text_infers_building_height():
    # Full pipeline: no explicit floor number anywhere, but the building
    # height plus "dernier étage" lets us deduce it.
    text = (
        "Au sein d'un bel immeuble haussmannien de six étages édifié en 1900, "
        "cet appartement offre un potentiel certain. "
        "Au dernier étage avec ascenseur."
    )
    info = parse_maison_et_appartement_floor_from_text(text)
    assert info.floor == 6
    assert info.is_top_floor is True


def test_parse_maison_et_appartement_floor_from_text_no_inference_without_top_floor():
    # The building-height inference should only kick in once we already
    # know it's the top floor — otherwise "six étages" alone says nothing
    # about which floor this specific unit is on.
    text = "Au sein d'un bel immeuble haussmannien de six étages édifié en 1900."
    info = parse_maison_et_appartement_floor_from_text(text)
    assert info.floor is None
    assert info.is_top_floor is None


def test_parse_maison_et_appartement_floor_from_text_none_input():
    info = parse_maison_et_appartement_floor_from_text(None)
    assert info.floor is None
    assert info.is_top_floor is None
