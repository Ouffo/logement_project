from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from src.ingestion.sources.bienici_source import (
    energy_class_from_dpe_score,
    get_bienici_energy_section,
    is_bienici_energy_not_submitted,
    parse_bienici_construction_year,
    parse_bienici_dpe_score,
    parse_bienici_energy_class,
    parse_bienici_energy_class_from_json,
    parse_bienici_energy_class_from_rating,
    parse_bienici_floor,
    parse_bienici_postal_code,
    parse_bienici_posted_at,
    parse_bienici_rooms,
    parse_bienici_search_html,
    parse_bienici_surface,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _real_detail_section():
    html = _read_fixture("bienici_detail_section_sample.html")
    return BeautifulSoup(html, "html.parser").select_one("section")


def test_parse_bienici_search_html_extracts_real_listings():
    # bienici_search_sample.html is a real (trimmed) capture of a bienici.com
    # search-results page, as saved by BieniciSource.fetch_html in production.
    html = _read_fixture("bienici_search_sample.html")

    listings = parse_bienici_search_html(html)

    assert len(listings) == 5
    assert all(listing.source == "bienici" for listing in listings)
    assert all(listing.price_eur > 0 for listing in listings)
    assert all(listing.surface_m2 > 0 for listing in listings)


def test_parse_bienici_search_html_specific_listing_fields():
    html = _read_fixture("bienici_search_sample.html")

    listings = {listing.source_id: listing for listing in parse_bienici_search_html(html)}

    listing = listings["ag751223-523557920"]
    assert listing.price_eur == 1155
    assert listing.surface_m2 == 28.0
    assert listing.postal_code == "75014"
    assert listing.city == "Paris"


def test_parse_bienici_search_html_deduplicates_by_data_id():
    html = """
    <article data-id="dup1">
        <a class="detailedSheetLink" href="/x1"></a>
        <div class="real-estate-main-info__title">Studio 25 m²</div>
        <div class="ad-price__the-price">900 €</div>
    </article>
    <article data-id="dup1">
        <a class="detailedSheetLink" href="/x1"></a>
        <div class="real-estate-main-info__title">Studio 25 m²</div>
        <div class="ad-price__the-price">900 €</div>
    </article>
    """

    listings = parse_bienici_search_html(html)

    assert len(listings) == 1


def test_parse_bienici_search_html_skips_listing_without_surface():
    html = """
    <article data-id="abc">
        <a class="detailedSheetLink" href="/x1"></a>
        <div class="real-estate-main-info__title">Studio sans surface indiquée</div>
        <div class="ad-price__the-price">900 €</div>
    </article>
    """

    assert parse_bienici_search_html(html) == []


def test_parse_bienici_search_html_defaults_to_paris_without_parseable_postal_code():
    # Regression test: a listing whose address has no recognizable "75XXX"
    # postal code used to crash the whole page (RentalListing.city isn't
    # optional) instead of just defaulting to the search's own Paris scope.
    html = """
    <article data-id="abc">
        <a class="detailedSheetLink" href="/x1"></a>
        <div class="real-estate-main-info__title">Studio 25 m²</div>
        <div class="real-estate-main-info__address">Adresse non standard</div>
        <div class="ad-price__the-price">900 €</div>
    </article>
    """

    listings = parse_bienici_search_html(html)

    assert len(listings) == 1
    assert listings[0].city == "Paris"
    assert listings[0].postal_code is None


def test_parse_bienici_search_html_skips_listing_without_link():
    html = """
    <article data-id="abc">
        <div class="real-estate-main-info__title">Studio 25 m²</div>
        <div class="ad-price__the-price">900 €</div>
    </article>
    """

    assert parse_bienici_search_html(html) == []


def test_parse_bienici_surface():
    assert parse_bienici_surface("Studio 28 m²") == 28.0


def test_parse_bienici_surface_no_match():
    assert parse_bienici_surface("Studio sans surface indiquée") is None


def test_parse_bienici_rooms():
    assert parse_bienici_rooms("Appartement 3 pièces") == 3


def test_parse_bienici_rooms_no_match():
    assert parse_bienici_rooms("Studio") is None


def test_parse_bienici_postal_code():
    assert parse_bienici_postal_code("12 rue de la paix 75011 Paris") == "75011"


def test_parse_bienici_postal_code_no_match():
    assert parse_bienici_postal_code("Adresse sans code postal") is None


def test_parse_bienici_postal_code_none_input():
    assert parse_bienici_postal_code(None) is None


def test_parse_bienici_energy_class_from_real_section():
    # bienici_detail_section_sample.html is a real (trimmed to a single
    # <section>) capture of a bienici.com detail page.
    assert parse_bienici_energy_class(_real_detail_section()) == "C"


def test_parse_bienici_construction_year_from_real_section():
    assert parse_bienici_construction_year(_real_detail_section()) == 1900


def test_parse_bienici_floor_from_real_section():
    # bienici_detail_section_sample.html has "1er étage (sur 3)"
    assert parse_bienici_floor(_real_detail_section()) == 1


def test_parse_bienici_floor_returns_none_without_match():
    html = '<section><div class="labelInfo"><span>Cave</span></div></section>'
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_floor(section) is None


def test_parse_bienici_floor_falls_back_to_description():
    html = """
    <section>
      <div class="labelInfo"><span>Cave</span></div>
      <section class="description">
        Au 1er étage, sans ascenseur, appartement lumineux.
      </section>
    </section>
    """
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_floor(section) == 1


def test_parse_bienici_floor_ignores_building_total_alone():
    # "1 étage" here means "this building has 1 floor", not the unit's
    # own floor — same ambiguity as "N étages" (plural) elsewhere.
    html = '<section><div class="labelInfo"><span>1 étage</span></div></section>'
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_floor(section) is None


def test_parse_bienici_posted_at_from_real_section():
    assert parse_bienici_posted_at(_real_detail_section()) == datetime(2026, 7, 1, tzinfo=UTC)


def test_get_bienici_energy_section_finds_real_section():
    assert get_bienici_energy_section(_real_detail_section()) is not None


def test_parse_bienici_dpe_score_from_real_section():
    energy_section = get_bienici_energy_section(_real_detail_section())
    assert parse_bienici_dpe_score(energy_section) == 156


def test_parse_bienici_energy_class_from_rating_real_section():
    energy_section = get_bienici_energy_section(_real_detail_section())
    assert parse_bienici_energy_class_from_rating(energy_section) == "C"


def test_is_bienici_energy_not_submitted_true():
    section = BeautifulSoup(
        '<section class="energySection">DPE non soumis</section>', "html.parser"
    ).select_one("section")

    assert is_bienici_energy_not_submitted(section) is True


def test_is_bienici_energy_not_submitted_false():
    section = get_bienici_energy_section(_real_detail_section())

    assert is_bienici_energy_not_submitted(section) is False


def test_parse_bienici_energy_class_returns_none_when_not_submitted():
    html = '<div><section class="energySection">DPE non soumis</section></div>'
    section = BeautifulSoup(html, "html.parser").select_one("div")

    assert parse_bienici_energy_class(section) is None


def test_parse_bienici_energy_class_from_json():
    html = '<section class="energySection"><script>{"energyClass":"D"}</script></section>'
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_energy_class_from_json(section) == "D"


def test_parse_bienici_dpe_score_consommation_pattern():
    html = '<section class="energySection">Consommation énergétique : 200 kWh/m2.an</section>'
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_dpe_score(section) == 200


def test_parse_bienici_dpe_score_diagnostic_pattern():
    html = (
        '<section class="energySection">'
        "Diagnostic de Performance Énergétique : 200 kWh/m2.an</section>"
    )
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_dpe_score(section) == 200


def test_parse_bienici_dpe_score_dpe_pattern():
    html = '<section class="energySection">DPE : 200 kWh/m2.an</section>'
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_dpe_score(section) == 200


def test_parse_bienici_dpe_score_ignores_energie_finale():
    # "énergie finale" readings use a different scale than the primary-energy
    # consumption score the rest of the app expects, so they're excluded.
    html = (
        '<section class="energySection">'
        "Consommation énergétique (énergie finale) : 200 kWh/m2.an</section>"
    )
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_dpe_score(section) is None


def test_parse_bienici_dpe_score_no_match():
    html = '<section class="energySection">Pas de DPE disponible</section>'
    section = BeautifulSoup(html, "html.parser").select_one("section")

    assert parse_bienici_dpe_score(section) is None


def test_energy_class_from_dpe_score_boundaries():
    cases = [
        (70, "A"),
        (71, "B"),
        (110, "B"),
        (111, "C"),
        (180, "C"),
        (181, "D"),
        (250, "D"),
        (251, "E"),
        (330, "E"),
        (331, "F"),
        (420, "F"),
        (421, "G"),
    ]

    for score, expected in cases:
        assert energy_class_from_dpe_score(score) == expected


def test_parse_bienici_construction_year_out_of_range_is_ignored():
    section = BeautifulSoup("<div>Construit en 1650</div>", "html.parser").select_one("div")

    assert parse_bienici_construction_year(section) is None


def test_parse_bienici_construction_year_no_match():
    section = BeautifulSoup("<div>Rien ici</div>", "html.parser").select_one("div")

    assert parse_bienici_construction_year(section) is None


def test_parse_bienici_posted_at_abbreviated_month():
    section = BeautifulSoup("<div>Publiée le 3 janv. 2026</div>", "html.parser").select_one("div")

    assert parse_bienici_posted_at(section) == datetime(2026, 1, 3, tzinfo=UTC)


def test_parse_bienici_posted_at_no_match():
    section = BeautifulSoup("<div>Rien ici</div>", "html.parser").select_one("div")

    assert parse_bienici_posted_at(section) is None
