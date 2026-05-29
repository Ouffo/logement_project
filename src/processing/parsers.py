import re

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