SEARCH_CRITERIA = {
    "city": "Paris",
    "preferred_areas": ["75013", "75014", "75015", "75005", "75006", "78140", "92130", "78210"],
    "max_price": 1200,
    "min_surface_m2": 25,
    "min_rooms": 2,
    "preferences": {"furnished": True, "parking": True, "quiet": True},
}

PURCHASE_SEARCH_CRITERIA = {
    "city": "Paris",
    "preferred_areas": [
        "75001",
        "75002",
        "75003",
        "75004",
        "75005",
        "75006",
        "75009",
        "75010",
        "75011",
        "75014",
    ],
    "max_price": 650000,
    "min_surface_m2": 50,
    "min_rooms": 3,
    "preferences": {"furnished": False, "parking": False, "quiet": True},
}


def get_search_criteria(is_rental: bool) -> dict:
    return SEARCH_CRITERIA if is_rental else PURCHASE_SEARCH_CRITERIA
