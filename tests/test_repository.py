from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import HttpUrl
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage.db import Base
from src.storage.models import RentalListing
from src.storage.orm_models import RentalListingORM
from src.storage.repository import (
    deduplicate_listings,
    enrich_listings,
    get_listings_to_enrich,
    get_listings_to_score_image,
    mark_missing_listings_inactive,
    save_listing,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db_session = session_factory()
    yield db_session
    db_session.close()


def _orm_listing(**overrides):
    defaults = dict(
        source="pap",
        source_id="1",
        url="http://example.com/1",
        title="Test",
        city="Paris",
        price_eur=1000,
        surface_m2=30,
        is_active=True,
    )
    defaults.update(overrides)
    return RentalListingORM(**defaults)


def _listing(**overrides):
    defaults = dict(
        source="pap",
        source_id="1",
        url=HttpUrl("http://example.com/1"),
        title="Test",
        city="Paris",
        price_eur=1000,
        surface_m2=30,
    )
    defaults.update(overrides)
    return RentalListing(**defaults)


def test_get_listings_to_enrich_excludes_already_enriched(session):
    now = datetime.now(UTC)
    pending = _orm_listing(source_id="1", details_fetched_at=None)
    done = _orm_listing(source_id="2", details_fetched_at=now)
    session.add_all([pending, done])
    session.commit()

    result = get_listings_to_enrich(session, "pap")

    assert [listing.source_id for listing in result] == ["1"]


def test_get_listings_to_enrich_excludes_other_sources(session):
    listing = _orm_listing(source="leboncoin", source_id="1", details_fetched_at=None)
    session.add(listing)
    session.commit()

    assert get_listings_to_enrich(session, "pap") == []


def test_get_listings_to_enrich_excludes_inactive(session):
    listing = _orm_listing(source_id="1", details_fetched_at=None, is_active=False)
    session.add(listing)
    session.commit()

    assert get_listings_to_enrich(session, "pap") == []


def test_get_listings_to_score_image_requires_image_url(session):
    no_image = _orm_listing(source_id="1", image_url=None, image_scored_at=None)
    with_image = _orm_listing(source_id="2", image_url="http://img", image_scored_at=None)
    session.add_all([no_image, with_image])
    session.commit()

    result = get_listings_to_score_image(session)

    assert [listing.source_id for listing in result] == ["2"]


def test_get_listings_to_score_image_excludes_already_scored(session):
    now = datetime.now(UTC)
    listing = _orm_listing(source_id="1", image_url="http://img", image_scored_at=now)
    session.add(listing)
    session.commit()

    assert get_listings_to_score_image(session) == []


def test_mark_missing_listings_inactive_deactivates_stale_listings(session):
    kept = _orm_listing(source_id="1", is_active=True)
    stale = _orm_listing(source_id="2", is_active=True)
    session.add_all([kept, stale])
    session.commit()

    latest = [_listing(source_id="1")]

    mark_missing_listings_inactive(session, "pap", latest)
    session.commit()

    assert kept.is_active is True
    assert stale.is_active is False


def test_mark_missing_listings_inactive_skips_when_no_latest_listings():
    # Guards against wiping out every listing if a fetch returns nothing
    # (e.g. the source was down) instead of treating it as "all gone".
    def _fail_if_queried(*_args, **_kwargs):
        raise AssertionError("should not query the database")

    session = SimpleNamespace(query=_fail_if_queried)

    mark_missing_listings_inactive(session, "pap", [])


def test_deduplicate_listings_removes_duplicates_by_source_and_id():
    a = SimpleNamespace(source="pap", source_id="1")
    b = SimpleNamespace(source="pap", source_id="1")
    c = SimpleNamespace(source="pap", source_id="2")

    assert deduplicate_listings([a, b, c]) == [a, c]


def test_deduplicate_listings_keeps_same_source_id_from_different_sources():
    a = SimpleNamespace(source="pap", source_id="1")
    b = SimpleNamespace(source="leboncoin", source_id="1")

    assert deduplicate_listings([a, b]) == [a, b]


class _FakeSource:
    def __init__(self, detail_storage_path, htmls_by_id):
        self.name = "fake"
        self.detail_storage_path = str(detail_storage_path)
        self._htmls_by_id = htmls_by_id
        self.enriched_ids = []

    def fetch_detail_htmls(self, listings):
        return [(listing, self._htmls_by_id[listing.source_id]) for listing in listings]

    def enrich_listing(self, listing, html):
        self.enriched_ids.append(listing.source_id)


def test_enrich_listings_skips_and_does_not_cache_empty_detail_page(tmp_path):
    # Regression: a failed/timed-out fetch (or a listing taken down between
    # extract-save and enrich) can come back as a near-empty shell like
    # "<html><head></head><body></body></html>" — caching that would
    # permanently poison the listing, since fetch_detail_htmls only
    # re-fetches when the cache file is missing.
    listing = _orm_listing(source_id="empty")
    source = _FakeSource(tmp_path, {"empty": "<html><head></head><body></body></html>"})

    enrich_listings(source, [listing])

    assert source.enriched_ids == []
    assert not (tmp_path / "empty.html").exists()


def test_enrich_listings_caches_and_enriches_valid_detail_page(tmp_path):
    listing = _orm_listing(source_id="valid")
    html = "<html><body>" + "x" * 1000 + "</body></html>"
    source = _FakeSource(tmp_path, {"valid": html})

    enrich_listings(source, [listing])

    assert source.enriched_ids == ["valid"]
    assert (tmp_path / "valid.html").read_text(encoding="utf-8") == html


def test_save_listing_creates_new_listing(session):
    listing = _listing(source_id="1")

    db_listing = save_listing(session, listing)
    session.commit()

    assert db_listing.id is not None
    assert db_listing.source_id == "1"
    assert db_listing.is_active is True


def test_save_listing_updates_existing_listing(session):
    existing = _orm_listing(source_id="1", title="Old title", price_eur=900)
    session.add(existing)
    session.commit()
    existing_id = existing.id

    updated = _listing(source_id="1", title="New title", price_eur=1200)

    db_listing = save_listing(session, updated)
    session.commit()

    assert db_listing.id == existing_id
    assert db_listing.title == "New title"
    assert db_listing.price_eur == 1200
