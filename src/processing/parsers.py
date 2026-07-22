import re
from datetime import UTC, datetime, timedelta


def parse_price(price_str: str) -> int | None:
    kept = re.sub(r"[^\d,.]", "", price_str)

    last_sep = max(kept.rfind(","), kept.rfind("."))
    if last_sep == -1:
        # No digits at all (e.g. a "Immobilier neuf" / "Prix sur demande"
        # placeholder instead of an actual price) — the caller is expected
        # to skip the listing rather than crash the whole batch on it.
        return int(kept) if kept else None

    integer_part = re.sub(r"[,.]", "", kept[:last_sep])
    fractional_part = kept[last_sep + 1 :]

    if not integer_part:
        return None

    if len(fractional_part) == 3:
        # the separator groups thousands (e.g. "1.200" or "1,200" -> 1200)
        return int(integer_part + fractional_part)

    # the separator is a decimal mark (e.g. "1300,50" -> 1300.50), cents are truncated
    return int(float(f"{integer_part}.{fractional_part}"))


def parse_surface(surface_str: str) -> float | None:
    # strip the unit ("m²" or the plain-ASCII "m2") so its trailing digit
    # doesn't get mistaken for part of the number
    surface_str = re.sub(r"m\s*[²2]\b", "", surface_str, flags=re.IGNORECASE)

    cleaned = re.sub(
        r"[^\d.]",
        "",
        surface_str.replace(",", "."),
    )

    # No digits at all — caller is expected to skip the listing rather than
    # crash the whole batch on it.
    return float(cleaned) if cleaned else None


def parse_rooms(rooms_str: str) -> int | None:
    cleaned = re.sub(
        r"[^\d]",
        "",
        rooms_str,
    )

    return int(cleaned) if cleaned else None


WEEKDAYS_FR = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}


def parse_french_posted_at(text: str) -> datetime | None:
    text = text.lower().strip()
    now = datetime.now(UTC)

    time_match = re.search(r"à\s+(\d{1,2})[:h](\d{2})", text)
    hour = int(time_match.group(1)) if time_match else 0
    minute = int(time_match.group(2)) if time_match else 0

    if "aujourd" in text:
        return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if "hier" in text:
        return (now - timedelta(days=1)).replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

    for weekday_name, weekday_index in WEEKDAYS_FR.items():
        if weekday_name in text and "dernier" in text:
            days_back = (now.weekday() - weekday_index) % 7
            if days_back == 0:
                days_back = 7

            return (now - timedelta(days=days_back)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

    date_match = re.search(
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
        text,
    )

    if date_match:
        day, month, year = map(int, date_match.groups())

        return datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=UTC,
        )

    return None
