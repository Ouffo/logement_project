import re
from datetime import UTC, datetime, timedelta

def parse_price(price_str: str) -> int:
    cleaned = re.sub(
        r"[^\d]",
        "",
        price_str,
    ).replace(",", ".")

    return int(cleaned)


def parse_surface(surface_str: str) -> float:
    cleaned = re.sub(
        r"[^\d.]",
        "",
        surface_str.replace(",", "."),
    )

    return float(cleaned)

def parse_rooms(rooms_str: str) -> int:
    cleaned = re.sub(
        r"[^\d]",
        "",
        rooms_str,
    )

    return int(cleaned)

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