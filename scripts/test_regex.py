import re

text = """Déjà Vu
Annonce déjà vue.
939 €
Prix: 939 €.
Autre · 1 pièce · 21m²
Meublé
Meublé
Paris 75006 Mabillon
Située à Paris 75006 Mabillon.
11/05/2026
Date de dépôt : 11/05/2026.
Pro
Vendeur professionnel.
    """

subject = "Agréable Studio meublé idéalement situé"

def test_detail_regex():
    details_match = re.search(
    r"""
    (Appartement|Studio|Loft|Duplex)      # type
    \s*·?\s*                              # séparateur optionnel
    (?:
        (?:(\d+)\s*pi[eè]ce[s]?\s*·\s*)?  # pièces optionnelles
        (\d+(?:[,.]\d+)?)\s*m[²2]            # surface
    )
    """,
        text + " " + subject,
        flags=re.IGNORECASE | re.VERBOSE,
    )

    print(details_match.groups() if details_match else None)

def test_description_regex():
    subject = "Recherche d’un appartement"
    description_match = re.search(
        r"(Appartement|Studio|Loft|Duplex)(?:.*?(\d+(?:[,.]\d+)?)\s*m[²2])?",
        subject,
        flags=re.IGNORECASE | re.VERBOSE,
    )

    print(description_match.groups() if description_match else None)

if __name__ == "__main__":
    test_detail_regex()
    #test_description_regex()