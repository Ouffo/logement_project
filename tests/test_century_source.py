from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.sources.century_source import (
    energy_class_from_consumption_score,
    energy_class_from_ges_score,
    parse_century_construction_year,
    parse_century_energy_class,
    parse_century_floor,
    parse_century_postal_code,
    parse_century_posted_at,
    parse_century_rooms,
    parse_century_sale_search_html,
    parse_century_search_html,
    parse_century_surface,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _real_detail_section():
    html = _read_fixture("century_detail_sample.html")
    return BeautifulSoup(html, "html.parser")


def test_parse_century_search_html_extracts_real_listings():
    # century_search_sample.html is a real (trimmed to 3 cards) capture of a
    # century21.fr search-results page, as saved by CenturySource.fetch_html.
    html = _read_fixture("century_search_sample.html")

    listings = parse_century_search_html(html)

    assert len(listings) == 3
    assert all(listing.source == "century" for listing in listings)
    assert all(listing.is_rental for listing in listings)
    assert all(listing.price_eur > 0 for listing in listings)
    assert all(listing.surface_m2 > 0 for listing in listings)


def test_parse_century_search_html_specific_listing_fields():
    html = _read_fixture("century_search_sample.html")

    listings = {listing.source_id: listing for listing in parse_century_search_html(html)}

    listing = listings["15843379089"]
    assert listing.price_eur == 1036
    assert listing.surface_m2 == 30.46
    assert listing.rooms == 1
    assert listing.postal_code == "75019"
    assert listing.city == "Paris"
    assert str(listing.url) == "https://www.century21.fr/trouver_logement/detail/15843379089/"


def test_parse_century_sale_search_html_forces_sale_fields():
    html = _read_fixture("century_search_sample.html")

    listings = parse_century_sale_search_html(html)

    assert len(listings) == 3
    assert all(listing.source == "century_sale" for listing in listings)
    assert all(listing.is_rental is False for listing in listings)


def test_parse_century_search_html_deduplicates_by_data_uid():
    html = """
    <div class="c-the-property-thumbnail-with-content" data-uid="dup1">
        <a href="/trouver_logement/detail/dup1/"></a>
        <h3>
            <div class="c-text-theme-heading-4">PARIS 75011
                <br/>25 m<sup>2</sup>, 1 pièce
            </div>
            <div class="c-text-theme-heading-3">Appartement Studio à louer</div>
        </h3>
        <div class="c-text-theme-heading-1">900 €</div>
    </div>
    <div class="c-the-property-thumbnail-with-content" data-uid="dup1">
        <a href="/trouver_logement/detail/dup1/"></a>
        <h3>
            <div class="c-text-theme-heading-4">PARIS 75011
                <br/>25 m<sup>2</sup>, 1 pièce
            </div>
            <div class="c-text-theme-heading-3">Appartement Studio à louer</div>
        </h3>
        <div class="c-text-theme-heading-1">900 €</div>
    </div>
    """

    listings = parse_century_search_html(html)

    assert len(listings) == 1


def test_parse_century_search_html_skips_listing_without_surface():
    html = """
    <div class="c-the-property-thumbnail-with-content" data-uid="abc">
        <a href="/trouver_logement/detail/abc/"></a>
        <h3><div class="c-text-theme-heading-4">PARIS 75011</div></h3>
        <div class="c-text-theme-heading-1">900 €</div>
    </div>
    """

    assert parse_century_search_html(html) == []


def test_parse_century_search_html_skips_listing_without_link():
    html = """
    <div class="c-the-property-thumbnail-with-content" data-uid="abc">
        <h3>
            <div class="c-text-theme-heading-4">PARIS 75011
                <br/>25 m<sup>2</sup>, 1 pièce
            </div>
        </h3>
        <div class="c-text-theme-heading-1">900 €</div>
    </div>
    """

    assert parse_century_search_html(html) == []


def test_parse_century_search_html_defaults_to_paris_without_parseable_postal_code():
    html = """
    <div class="c-the-property-thumbnail-with-content" data-uid="abc">
        <a href="/trouver_logement/detail/abc/"></a>
        <h3>
            <div class="c-text-theme-heading-4">Adresse non standard
                <br/>25 m<sup>2</sup>, 1 pièce
            </div>
            <div class="c-text-theme-heading-3">Appartement Studio à louer</div>
        </h3>
        <div class="c-text-theme-heading-1">900 €</div>
    </div>
    """

    listings = parse_century_search_html(html)

    assert len(listings) == 1
    assert listings[0].city == "Paris"
    assert listings[0].postal_code is None


def test_parse_century_surface():
    assert parse_century_surface("30,46 m 2 , 1 pièce") == 30.46


def test_parse_century_surface_no_match():
    assert parse_century_surface("Studio sans surface indiquée") is None


def test_parse_century_rooms():
    assert parse_century_rooms(", 3 pièces") == 3


def test_parse_century_rooms_no_match():
    assert parse_century_rooms("Studio") is None


def test_parse_century_postal_code():
    assert parse_century_postal_code("PARIS\xa0  75019") == "75019"


def test_parse_century_postal_code_extra_city():
    assert parse_century_postal_code("VÉLIZY-VILLACOUBLAY\xa0  78140") == "78140"


def test_parse_century_postal_code_no_match():
    assert parse_century_postal_code("Adresse sans code postal") is None


def test_parse_century_postal_code_none_input():
    assert parse_century_postal_code(None) is None


def test_parse_century_energy_class_from_real_section():
    # century_detail_sample.html is a real capture (Étage: 2ème, DPE 203
    # kWh/m².an / 62 kgCO2/m².an -> worse-of-two is E) of a century21.fr
    # sale detail page.
    assert parse_century_energy_class(_real_detail_section()) == "E"


def test_parse_century_energy_class_missing_dpe_section():
    section = BeautifulSoup("<div>Rien ici</div>", "html.parser")
    assert parse_century_energy_class(section) is None


def test_energy_class_from_consumption_score_boundaries():
    cases = [(70, "A"), (71, "B"), (180, "C"), (181, "D"), (420, "F"), (421, "G")]
    for score, expected in cases:
        assert energy_class_from_consumption_score(score) == expected


def test_energy_class_from_ges_score_boundaries():
    cases = [(6, "A"), (7, "B"), (30, "C"), (31, "D"), (100, "F"), (101, "G")]
    for score, expected in cases:
        assert energy_class_from_ges_score(score) == expected


def test_parse_century_construction_year_from_real_section():
    assert parse_century_construction_year(_real_detail_section()) == 1970


def test_parse_century_construction_year_no_match():
    html = '<ul class="c-the-property-detail-global-view__list"><li>Rien ici</li></ul>'
    section = BeautifulSoup(html, "html.parser")
    assert parse_century_construction_year(section) is None


def test_parse_century_construction_year_out_of_range_is_ignored():
    html = (
        '<ul class="c-the-property-detail-global-view__list">'
        "<li>Année construction : 1650</li></ul>"
    )
    section = BeautifulSoup(html, "html.parser")
    assert parse_century_construction_year(section) is None


def test_parse_century_floor_from_real_section():
    # century_detail_sample.html has "Étage : 2 ème"
    info = parse_century_floor(_real_detail_section())
    assert info.floor == 2
    assert info.is_top_floor is None


def test_parse_century_floor_rdc():
    html = (
        '<ul class="c-the-property-detail-global-view__list"><li>Étage : Rez-de-chaussée</li></ul>'
    )
    section = BeautifulSoup(html, "html.parser")

    info = parse_century_floor(section)
    assert info.floor == 0


def test_parse_century_floor_ordinal_label_first():
    html = '<ul class="c-the-property-detail-global-view__list"><li>Étage : 9 ème</li></ul>'
    section = BeautifulSoup(html, "html.parser")

    info = parse_century_floor(section)
    assert info.floor == 9
    assert info.is_top_floor is None


def test_parse_century_floor_ordinal_er_suffix():
    # "1 er" (1er = first floor) uses a different ordinal suffix than "ème",
    # and used to be missed entirely (floor stayed None).
    html = '<ul class="c-the-property-detail-global-view__list"><li>Étage : 1 er</li></ul>'
    section = BeautifulSoup(html, "html.parser")

    info = parse_century_floor(section)
    assert info.floor == 1


def test_parse_century_floor_falls_back_to_description_for_top_floor():
    # Regression: Century's structured "Étage" field never states whether
    # it's the top floor (e.g. "Étage : 7 ème" for an 8-floor building) —
    # that only ever appears as free text in the description ("en dernier
    # étage"), which used to be ignored entirely by parse_century_floor.
    html = """
    <div>
      <ul class="c-the-property-detail-global-view__list"><li>Étage : 7 ème</li></ul>
      <section class="c-the-property-detail-description">
        <div>Appartement de trois pièces en dernier étage aux vues dégagées.</div>
      </section>
    </div>
    """
    section = BeautifulSoup(html, "html.parser")

    info = parse_century_floor(section)
    assert info.floor == 7
    assert info.is_top_floor is True


def test_parse_century_floor_returns_none_without_match():
    html = '<ul class="c-the-property-detail-global-view__list"><li>Studio</li></ul>'
    section = BeautifulSoup(html, "html.parser")

    info = parse_century_floor(section)
    assert info.floor is None
    assert info.is_top_floor is None


def test_parse_century_posted_at_always_none():
    # Century21 detail pages don't expose a publication date.
    assert parse_century_posted_at(_real_detail_section()) is None
