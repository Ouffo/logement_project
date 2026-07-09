from datetime import UTC, datetime
from pathlib import Path

from src.ingestion.sources.leboncoin_source import (
    extract_subject_by_source_id,
    is_plausible_construction_year,
    parse_construction_year_from_json_like_text,
    parse_leboncoin_construction_year,
    parse_leboncoin_energy,
    parse_leboncoin_posted_at,
    parse_leboncoin_posted_at_from_json,
    parse_leboncoin_posted_at_from_visible_text,
    parse_leboncoin_search_html,
    parse_location,
    parse_rooms,
    parse_rooms_and_surface,
    parse_source_id,
    parse_surface_m2,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_parse_rooms_and_surface_with_superscript_m2():
    rooms, surface = parse_rooms_and_surface("Bel appartement 3 pièces 28 m² lumineux")
    assert rooms == 3
    assert surface == 28.0


def test_parse_rooms_and_surface_with_ascii_m2():
    # Leboncoin sometimes renders the unit without the superscript "²",
    # e.g. "31 m2 SANS VIS" — this must not be silently dropped.
    rooms, surface = parse_rooms_and_surface("31 m2 SANS VIS 3 pieces")
    assert rooms == 3
    assert surface == 31.0


def test_parse_rooms_and_surface_no_match_returns_none():
    rooms, surface = parse_rooms_and_surface("Description sans ces informations")
    assert rooms is None
    assert surface is None


def test_parse_leboncoin_search_html_extracts_real_listings():
    # leboncoin_search_sample.html is a real (trimmed) capture of a
    # leboncoin.fr search-results page, as saved by LeboncoinSource.fetch_html
    # in production.
    html = _read_fixture("leboncoin_search_sample.html")

    listings = parse_leboncoin_search_html(html)

    assert len(listings) == 5
    assert all(listing.source == "leboncoin" for listing in listings)
    assert all(listing.price_eur > 0 for listing in listings)
    assert all(listing.surface_m2 > 0 for listing in listings)


def test_parse_leboncoin_search_html_specific_listing_fields():
    html = _read_fixture("leboncoin_search_sample.html")

    listings = {listing.source_id: listing for listing in parse_leboncoin_search_html(html)}

    listing = listings["3224771183"]
    assert listing.price_eur == 1060
    assert listing.surface_m2 == 26.0
    assert listing.rooms == 1


def test_parse_leboncoin_search_html_skips_listing_without_property_type():
    html = """
    <article>
        <a href="/ad/locations/123">Recherche colocataire, budget 900€</a>
    </article>
    """

    assert parse_leboncoin_search_html(html) == []


def test_parse_leboncoin_search_html_deduplicates_by_url():
    html = """
    <article>
        <a href="/ad/locations/123">Studio 25 m², 900 €</a>
    </article>
    <article>
        <a href="/ad/locations/123">Studio 25 m², 900 €</a>
    </article>
    """

    listings = parse_leboncoin_search_html(html)

    assert len(listings) == 1


def test_parse_location_finds_paris_postal_code():
    assert parse_location("Description Paris 75011 Belleville") == ("Paris", "75011")


def test_parse_location_no_match():
    assert parse_location("Description sans localisation") == ("Paris", None)


def test_parse_source_id_strips_trailing_slash():
    url = "https://www.leboncoin.fr/ad/locations/3224771183"
    assert parse_source_id(url) == "3224771183"
    assert parse_source_id(url + "/") == "3224771183"


def test_extract_subject_by_source_id():
    html = '{"list_id": 123, "other": 1, "subject": "Bel appartement"}'
    assert extract_subject_by_source_id(html) == {"123": "Bel appartement"}


def test_extract_subject_by_source_id_no_match():
    assert extract_subject_by_source_id("{}") == {}


def test_parse_rooms():
    assert parse_rooms("Appartement 3 pièces") == 3


def test_parse_rooms_no_match():
    assert parse_rooms("Studio") is None


def test_parse_surface_m2():
    assert parse_surface_m2("Surface 28,5 m²") == 28.5


def test_parse_surface_m2_no_match():
    assert parse_surface_m2("Pas de surface") is None


def test_parse_leboncoin_energy_dom_fallback():
    html = (
        '<div data-qa-id="criteria_item_energy_rate">'
        "<span>Classe</span><span>C</span></div>"
    )
    assert parse_leboncoin_energy(html) == "C"


def test_parse_leboncoin_energy_no_match():
    assert parse_leboncoin_energy("<div>rien</div>") is None


def test_parse_construction_year_from_json_like_text():
    assert parse_construction_year_from_json_like_text('{"constructionYear": 1965}') == 1965


def test_parse_construction_year_from_json_like_text_no_match():
    assert parse_construction_year_from_json_like_text('{"nothing": 1}') is None


def test_is_plausible_construction_year_boundaries():
    assert is_plausible_construction_year(1700) is True
    assert is_plausible_construction_year(1699) is False
    assert is_plausible_construction_year(2030) is True
    assert is_plausible_construction_year(2031) is False


def test_parse_leboncoin_posted_at_from_visible_text_aujourdhui():
    result = parse_leboncoin_posted_at_from_visible_text("Publié aujourd'hui à 14:30")
    today = datetime.now(UTC).date()
    assert result == datetime(today.year, today.month, today.day, 14, 30, tzinfo=UTC)


def test_parse_leboncoin_posted_at_from_visible_text_explicit_date():
    result = parse_leboncoin_posted_at_from_visible_text("Publié le 05/03/2026 à 18:45")
    assert result == datetime(2026, 3, 5, 18, 45, tzinfo=UTC)


def test_parse_leboncoin_posted_at_from_visible_text_heures_format():
    result = parse_leboncoin_posted_at_from_visible_text("Publié aujourd'hui à 14 heures 30")
    today = datetime.now(UTC).date()
    assert result == datetime(today.year, today.month, today.day, 14, 30, tzinfo=UTC)


def test_parse_leboncoin_posted_at_from_visible_text_no_match():
    assert parse_leboncoin_posted_at_from_visible_text("Rien ici") is None


def test_parse_leboncoin_posted_at_from_json_no_match():
    assert parse_leboncoin_posted_at_from_json("rien du tout") is None


def test_parse_leboncoin_construction_year_from_real_snippet():
    # leboncoin_detail_energy_year_posted_sample.html is a small real
    # (trimmed) capture of a leboncoin.fr detail page's construction-year,
    # energy-rate and posted-at data, as used by LeboncoinSource.enrich_listing.
    html = _read_fixture("leboncoin_detail_energy_year_posted_sample.html")
    assert parse_leboncoin_construction_year(html) == 1980


def test_parse_leboncoin_energy_from_real_snippet():
    html = _read_fixture("leboncoin_detail_energy_year_posted_sample.html")
    assert parse_leboncoin_energy(html) == "B"


def test_parse_leboncoin_posted_at_from_real_snippet():
    html = _read_fixture("leboncoin_detail_energy_year_posted_sample.html")
    assert parse_leboncoin_posted_at(html) == datetime(2026, 4, 28, 19, 24, 17, tzinfo=UTC)
