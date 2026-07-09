from src.utils.scrapping import (
    combine_htmls,
    extract_body_content,
    extract_leboncoin_search_content,
)


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
