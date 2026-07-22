from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from pydantic import HttpUrl

from src.ingestion.sources.pap_source import (
    merge_pap_list_and_detail,
    parse_pap_detail_html,
    parse_pap_energy_class,
    parse_pap_html,
    parse_pap_posted_at,
    parse_pap_source_id,
)
from src.storage.models import RentalListing

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _real_detail_sections():
    html = _read_fixture("pap_detail_sample.html")
    soup = BeautifulSoup(html, "html.parser")
    return {
        parse_pap_source_id(section.get("data-url")): section
        for section in soup.select("section.listing-detail")
    }


def test_parse_pap_detail_html_extracts_real_listings():
    # pap_detail_sample.html is a real (trimmed) capture of pap.fr detail
    # pages, as combined by PapSource.fetch_html in production.
    html = _read_fixture("pap_detail_sample.html")

    listings = parse_pap_detail_html(html)

    assert len(listings) == 5
    assert all(listing.source == "pap" for listing in listings)
    assert all(listing.price_eur > 0 for listing in listings)
    assert all(listing.surface_m2 > 0 for listing in listings)


def test_parse_pap_detail_html_specific_listing_fields():
    html = _read_fixture("pap_detail_sample.html")

    listings = {listing.source_id: listing for listing in parse_pap_detail_html(html)}

    listing = listings["r461300798"]
    assert listing.price_eur == 1020
    assert listing.surface_m2 == 26.0
    assert listing.rooms == 2
    assert listing.city == "Paris"
    assert listing.floor == 1
    assert listing.is_top_floor is None


def test_parse_pap_detail_html_skips_section_without_url():
    html = "<html><body><section class='listing-detail'><h1>x</h1></section></body></html>"

    assert parse_pap_detail_html(html) == []


def test_parse_pap_detail_html_skips_section_without_surface():
    html = """
    <section class="listing-detail" data-url="https://www.pap.fr/annonces/x-r1">
        <h1>Studio <span>900 €</span></h1>
        <h2>Paris 75011</h2>
    </section>
    """

    assert parse_pap_detail_html(html) == []


def test_parse_pap_detail_html_skips_non_numeric_price():
    # Regression: parse_price used to raise ValueError on non-numeric price
    # text, crashing the whole extract-save batch instead of just skipping
    # this one listing.
    html = """
    <section class="listing-detail" data-url="https://www.pap.fr/annonces/x-r1">
        <h1>Vente appartement <span>Prix sur demande</span></h1>
        <h2>Paris 75011</h2>
        <strong>3 pièces</strong>
        <strong>51 m²</strong>
    </section>
    """

    assert parse_pap_detail_html(html) == []


def test_parse_pap_detail_html_ignores_price_per_m2_fact():
    # Sale listings show a "X € le m²" fact alongside the real surface;
    # both contain "m²" so the price-per-m² one must not overwrite surface.
    html = """
    <section class="listing-detail" data-url="https://www.pap.fr/annonces/x-r1">
        <h1>Vente appartement <span>500 000 €</span></h1>
        <h2>Paris 75011</h2>
        <strong>3 pièces</strong>
        <strong>51 m²</strong>
        <strong>9.803 € le m²</strong>
    </section>
    """

    listings = parse_pap_detail_html(html)

    assert listings[0].surface_m2 == 51.0


def test_parse_pap_detail_html_ignores_price_per_m2_fact_spelled_out_currency():
    # Same as above, but with "euros" spelled out instead of "€" — the
    # exclusion must not depend on the currency symbol specifically.
    html = """
    <section class="listing-detail" data-url="https://www.pap.fr/annonces/x-r1">
        <h1>Vente appartement <span>500 000 €</span></h1>
        <h2>Paris 75011</h2>
        <strong>3 pièces</strong>
        <strong>51 m²</strong>
        <strong>9 803 euros le m²</strong>
    </section>
    """

    listings = parse_pap_detail_html(html)

    assert listings[0].surface_m2 == 51.0


def test_parse_pap_html_extracts_search_result_listing():
    # No real PAP search-results capture exists under data/raw/ (fetch_html
    # never persists it to disk, it's parsed in-memory), so this snippet is
    # hand-built to mirror the selectors parse_pap_html relies on.
    html = """
    <html><body>
    <div class="search-list-item-alt">
        <a class="item-title" href="/annonce/appartement-paris-12e-r123456789">
            Bel appartement
        </a>
        <div class="h1">Paris 12e</div>
        <div class="item-price">1 100 €</div>
        <div class="item-description">Appartement meublé calme avec parking</div>
        <ul class="item-tags">
            <li>2 pièces</li>
            <li>1 chambre</li>
            <li>30 m²</li>
        </ul>
        <img src="https://cdn.pap.fr/photo.jpg">
    </div>
    </body></html>
    """

    listings = parse_pap_html(html)

    assert len(listings) == 1
    listing = listings[0]
    assert listing.source_id == "r123456789"
    assert listing.price_eur == 1100
    assert listing.surface_m2 == 30.0
    assert listing.rooms == 2
    assert listing.bedrooms == 1
    assert listing.furnished is True
    assert listing.parking is True
    assert listing.quiet is True
    assert listing.image_url == "https://cdn.pap.fr/photo.jpg"


def test_parse_pap_source_id_strips_trailing_slash():
    url = "https://www.pap.fr/annonces/appartement-paris-17e-75017-r461300798"
    assert parse_pap_source_id(url) == "r461300798"
    assert parse_pap_source_id(url + "/") == "r461300798"


def test_parse_pap_energy_class_from_real_section():
    # pap_detail_sample.html is a real (trimmed) capture of pap.fr detail
    # pages; r461300798 genuinely displays energy class "E".
    section = _real_detail_sections()["r461300798"]
    assert parse_pap_energy_class(section) == "E"


def test_parse_pap_energy_class_missing_on_real_section():
    section = _real_detail_sections()["r444001934"]
    assert parse_pap_energy_class(section) is None


def test_parse_pap_energy_class_no_energy_block_at_all():
    section = BeautifulSoup("<section><p>Pas d'info énergie ici</p></section>", "html.parser")
    assert parse_pap_energy_class(section) is None


def test_parse_pap_posted_at_from_real_text():
    section = _real_detail_sections()["r461300798"]
    full_text = section.get_text("\n", strip=True)

    assert parse_pap_posted_at(full_text) == datetime(2026, 7, 4, tzinfo=UTC)


def test_parse_pap_posted_at_unaccented_month():
    assert parse_pap_posted_at("Mise à jour le 3 fevrier 2026") == datetime(2026, 2, 3, tzinfo=UTC)


def test_parse_pap_posted_at_no_match():
    assert parse_pap_posted_at("Aucune date ici") is None


def _listing(**overrides):
    defaults = dict(
        source="pap",
        source_id="1",
        url=HttpUrl("http://example.com/1"),
        title="List title",
        city="Paris",
        price_eur=1000,
        surface_m2=25,
    )
    defaults.update(overrides)
    return RentalListing(**defaults)


def test_merge_pap_list_and_detail_prefers_detail_fields():
    list_listing = _listing(source_id="1", title="List title", price_eur=1000, surface_m2=25)
    detail_listing = _listing(
        source_id="1",
        title="Detail title",
        price_eur=1100,
        surface_m2=30,
        furnished=True,
        parking=False,
    )

    merged = merge_pap_list_and_detail([list_listing], [detail_listing])

    assert len(merged) == 1
    assert merged[0].title == "Detail title"
    assert merged[0].price_eur == 1100
    assert merged[0].surface_m2 == 30.0
    assert merged[0].furnished is True
    assert merged[0].parking is False  # False is a real value, not "missing"


def test_merge_pap_list_and_detail_keeps_orphan_details():
    detail_listing = _listing(source_id="2", title="Orphan")

    merged = merge_pap_list_and_detail([], [detail_listing])

    assert len(merged) == 1
    assert merged[0].source_id == "2"


def test_parse_pap_html_skips_listing_without_price():
    html = """
    <html><body>
    <div class="search-list-item-alt">
        <a class="item-title" href="/annonce/x-r1">Bel appartement</a>
        <div class="h1">Paris 12e</div>
        <div class="item-price"></div>
        <div class="item-description">Description</div>
    </div>
    </body></html>
    """

    assert parse_pap_html(html) == []


def test_parse_pap_html_skips_non_numeric_price():
    # Regression: parse_price used to raise ValueError on non-numeric price
    # text (e.g. "Immobilier neuf" for a "programme neuf" listing).
    html = """
    <html><body>
    <div class="search-list-item-alt">
        <a class="item-title" href="/annonce/x-r1">Bel appartement</a>
        <div class="h1">Paris 12e</div>
        <div class="item-price">Immobilier neuf</div>
        <div class="item-description">Description</div>
        <ul class="item-tags">
            <li>30 m²</li>
        </ul>
    </div>
    </body></html>
    """

    assert parse_pap_html(html) == []
