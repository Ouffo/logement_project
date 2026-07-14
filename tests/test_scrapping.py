from src.utils.scrapping import (
    combine_htmls,
    extract_body_content,
    extract_leboncoin_search_content,
    parse_floor,
)


def test_parse_floor_none_input():
    assert parse_floor(None) is None


def test_parse_floor_no_match():
    assert parse_floor("sans info") is None


def test_parse_floor_er_suffix():
    assert parse_floor("1er étage") == 1


def test_parse_floor_e_suffix():
    assert parse_floor("2e étage") == 2


def test_parse_floor_eme_suffix():
    assert parse_floor("3ème étage") == 3


def test_parse_floor_accepts_unaccented_text():
    assert parse_floor("3eme etage") == 3


def test_parse_floor_rez_de_chaussee_returns_zero():
    assert parse_floor("rez-de-chaussée") == 0


def test_parse_floor_rez_de_chaussee_without_accent():
    assert parse_floor("rez-de-chaussee") == 0


def test_parse_floor_superscript_e_suffix():
    assert parse_floor("4ᵉ étage") == 4


def test_parse_floor_superscript_er_suffix():
    assert parse_floor("1ᵉʳ étage") == 1


def test_parse_floor_dernier_etage_uses_building_total():
    assert parse_floor("Dernier étage (sur 5)") == 5


def test_parse_floor_negative_basement():
    assert parse_floor("-1e étage") == -1


def test_parse_floor_ignores_building_total_alone():
    assert parse_floor("3 étages") is None
    assert parse_floor("1 étage") is None


def test_parse_floor_ignores_number_with_sur_suffix():
    assert parse_floor("2e étage (sur 8)") == 2


def test_parse_floor_dernier_et_dernier_etage():
    assert parse_floor("Au 4ème et dernier étage, clair et calme.") == 4


def test_parse_floor_au_prefix_without_etage_word():
    assert parse_floor("Studio meublé, au 2e ascenseur, proche commerces") == 2


def test_parse_floor_spelled_out_ordinal():
    assert parse_floor("Bel appartement situé au deuxième étage avec vue") == 2


def test_parse_floor_ignores_arrondissement_mention():
    assert parse_floor("Dans le beau 18e, studio entièrement rénové") is None


def test_parse_floor_seloger_ratio_format():
    assert parse_floor("Étage 4/6") == 4


def test_parse_floor_seloger_ratio_negative_basement():
    assert parse_floor("Étage -1/4") == -1


def test_parse_floor_seloger_ratio_negative_equals_total_is_top_floor():
    assert parse_floor("Étage -3/3") == 3


def test_parse_floor_rdc():
    assert parse_floor("RDC") == 0


def test_parse_floor_rdc_with_total():
    assert parse_floor("RDC/4") == 0


def test_parse_floor_bare_number_with_au_prefix():
    assert parse_floor("Situé au 2 étage d'une résidence avec ascenseur") == 2


def test_parse_floor_bare_number_ignores_dates():
    assert parse_floor("Libre au 15 juillet, résidence calme") is None


def test_parse_floor_ignores_plural_even_with_au():
    # "étages" (building total) shouldn't be confused with "étage"
    # (this listing's floor), even preceded by "au".
    assert parse_floor("au 3 étages") is None


def test_extract_body_content_removes_boilerplate_tags():
    html = """
    <html><body>
    <header>Header</header>
    <nav>Nav</nav>
    <script>var x = 1;</script>
    <footer>Footer</footer>
    <main><p>Bel appartement lumineux</p></main>
    </body></html>
    """
    result = extract_body_content(html)

    assert "Header" not in result
    assert "Nav" not in result
    assert "var x" not in result
    assert "Footer" not in result
    assert "Bel appartement lumineux" in result


def test_extract_body_content_removes_cookie_and_modal_elements():
    html = """
    <html><body><main>
    <div id="cookie-banner">Accept cookies</div>
    <div class="consent-popup">Consent</div>
    <p>Annonce réelle</p>
    </main></body></html>
    """
    result = extract_body_content(html)

    assert "Accept cookies" not in result
    assert "Consent" not in result
    assert "Annonce réelle" in result


def test_extract_body_content_removes_known_boilerplate_text():
    html = """
    <html><body><main>
    <p>Le bailleur a été notifié de votre message.</p>
    <p>Bel appartement lumineux</p>
    </main></body></html>
    """
    result = extract_body_content(html)

    assert "bailleur a été notifié" not in result
    assert "Bel appartement lumineux" in result


def test_extract_body_content_deduplicates_images():
    html = """
    <html><body><main>
    <img src="a.jpg">
    <img src="a.jpg">
    <img src="b.jpg">
    </main></body></html>
    """
    result = extract_body_content(html)

    assert result.count('src="a.jpg"') == 1
    assert result.count('src="b.jpg"') == 1


def test_extract_body_content_removes_images_without_src():
    html = """
    <html><body><main>
    <img alt="no source">
    <img src="b.jpg">
    </main></body></html>
    """
    result = extract_body_content(html)

    assert "no source" not in result
    assert 'src="b.jpg"' in result


def test_extract_body_content_removes_empty_links():
    html = """
    <html><body><main>
    <a href=""></a>
    <a href="/contact">Contact</a>
    </main></body></html>
    """
    result = extract_body_content(html)

    assert result.count("<a") == 1
    assert "Contact" in result


def test_extract_body_content_removes_empty_containers():
    html = """
    <html><body><main>
    <div></div>
    <p>Texte utile</p>
    <span>   </span>
    </main></body></html>
    """
    result = extract_body_content(html)

    assert "<div>" not in result
    assert "<span>" not in result
    assert "Texte utile" in result


def test_extract_body_content_strips_disallowed_attributes():
    html = """
    <html><body><main>
    <p onclick="track()" data-id="42" class="listing">Texte</p>
    </main></body></html>
    """
    result = extract_body_content(html)

    assert "onclick" not in result
    assert "data-id" not in result
    assert 'class="listing"' in result


def test_extract_body_content_removes_html_comments():
    html = """
    <html><body><main>
    <!-- a hidden comment -->
    <p>Texte visible</p>
    </main></body></html>
    """
    result = extract_body_content(html)

    assert "hidden comment" not in result
    assert "Texte visible" in result


def test_extract_leboncoin_search_content_keeps_only_rental_articles():
    html = """
    <html><body>
    <article><a href="/ad/locations/123">Listing 1</a></article>
    <article><a href="/other/456">Not a rental</a></article>
    <article><a href="/ad/locations/789">Listing 2</a></article>
    </body></html>
    """
    result = extract_leboncoin_search_content(html)

    assert "Listing 1" in result
    assert "Listing 2" in result
    assert "Not a rental" not in result


def test_extract_leboncoin_search_content_no_matching_articles():
    html = "<html><body><article><a href='/other/456'>Nope</a></article></body></html>"
    result = extract_leboncoin_search_content(html)

    assert "Nope" not in result
    assert "leboncoin-search-results" in result


def test_combine_htmls_wraps_each_page_in_a_labeled_section():
    result = combine_htmls(
        [("http://a.com", "<p>A</p>"), ("http://b.com", "<p>B</p>")],
        "listing",
    )

    assert '<section class="listing" data-url="http://a.com">' in result
    assert '<section class="listing" data-url="http://b.com">' in result
    assert "<p>A</p>" in result
    assert "<p>B</p>" in result


def test_combine_htmls_empty_list():
    result = combine_htmls([], "listing")

    assert "<html>" in result
    assert "<section" not in result
