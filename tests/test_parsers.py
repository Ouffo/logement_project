from datetime import UTC, datetime

import pytest

import src.processing.parsers as parsers_module
from src.processing.parsers import (
    parse_french_posted_at,
    parse_price,
    parse_rooms,
    parse_surface,
)


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 7, 8, 15, 0, 0, tzinfo=tz)  # a Wednesday


@pytest.fixture
def fixed_now(monkeypatch):
    monkeypatch.setattr(parsers_module, "datetime", _FixedDateTime)
    return datetime(2026, 7, 8, 15, 0, 0, tzinfo=UTC)


def test_parse_price_strips_currency_and_spaces():
    assert parse_price("1 200 €") == 1200


def test_parse_price_plain_digits():
    assert parse_price("1300€") == 1300


def test_parse_price_with_decimal_comma_truncates_cents():
    assert parse_price("1 300,50 €") == 1300


def test_parse_price_with_period_as_thousands_separator():
    # PAP renders prices like this, e.g. "1.200 €" for 1200 euros
    assert parse_price("1.200 €") == 1200


def test_parse_price_with_comma_as_thousands_separator():
    assert parse_price("1,200 €") == 1200


def test_parse_price_with_thousands_and_decimal_separator():
    assert parse_price("1.200,50 €") == 1200


def test_parse_price_with_nbsp_separators():
    # Leboncoin renders prices with a narrow no-break space (U+202F) between
    # thousands and a regular no-break space (U+00A0) before the currency sign
    price_str = "1" + chr(0x202F) + "170" + chr(0xA0) + "€"
    assert parse_price(price_str) == 1170


def test_parse_surface_plain_digits():
    assert parse_surface("30 m²") == 30.0


def test_parse_surface_with_decimal_comma():
    assert parse_surface("30,5 m²") == 30.5


def test_parse_surface_ascii_m2_unit_suffix():
    assert parse_surface("12.5m2") == 12.5


def test_parse_surface_ascii_m2_unit_suffix_no_decimal():
    assert parse_surface("50m2") == 50.0


def test_parse_surface_ascii_m2_with_decimal_comma():
    assert parse_surface("27,02 m2") == 27.02


def test_parse_rooms_with_word_suffix():
    assert parse_rooms("3 pièces") == 3


def test_parse_rooms_with_type_prefix():
    assert parse_rooms("T2") == 2


def test_parse_french_posted_at_aujourdhui(fixed_now):
    result = parse_french_posted_at("Aujourd'hui à 14:30")
    assert result == fixed_now.replace(hour=14, minute=30, second=0, microsecond=0)


def test_parse_french_posted_at_hier(fixed_now):
    result = parse_french_posted_at("Hier à 09:15")
    expected = datetime(2026, 7, 7, 9, 15, tzinfo=UTC)
    assert result == expected


def test_parse_french_posted_at_weekday_dernier(fixed_now):
    result = parse_french_posted_at("Lundi dernier à 10:00")
    assert result == datetime(2026, 7, 6, 10, 0, tzinfo=UTC)


def test_parse_french_posted_at_same_weekday_dernier_goes_back_a_full_week(fixed_now):
    # "today" (fixed_now) is a Wednesday, so "mercredi dernier" must resolve
    # to a week ago, not to today.
    result = parse_french_posted_at("Mercredi dernier à 08:00")
    assert result == datetime(2026, 7, 1, 8, 0, tzinfo=UTC)


def test_parse_french_posted_at_explicit_date():
    result = parse_french_posted_at("Publié le 05/03/2024")
    assert result == datetime(2024, 3, 5, 0, 0, tzinfo=UTC)


def test_parse_french_posted_at_explicit_date_with_time():
    result = parse_french_posted_at("Publié le 05/03/2024 à 18h45")
    assert result == datetime(2024, 3, 5, 18, 45, tzinfo=UTC)


def test_parse_french_posted_at_no_match_returns_none():
    assert parse_french_posted_at("il y a longtemps") is None
