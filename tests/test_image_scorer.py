from datetime import datetime
from types import SimpleNamespace

import httpx
from anthropic.types import TextBlock

from src.scoring import image_scorer
from src.scoring.image_scorer import score_listing_image


def _listing(**overrides):
    defaults = dict(source_id="1", image_url="http://example.com/photo.jpg")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _fake_response(status_code=200, content_type="image/jpeg", content=b"fake-bytes"):
    return SimpleNamespace(
        status_code=status_code,
        headers={"content-type": content_type},
        content=content,
    )


def _fake_anthropic_result(text):
    return SimpleNamespace(content=[TextBlock(type="text", text=text)])


def test_score_listing_image_no_image_url(monkeypatch):
    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("should not fetch when there is no image_url")

    monkeypatch.setattr(image_scorer.httpx, "get", _fail_if_called)

    listing = _listing(image_url=None)
    score_listing_image(listing)

    assert listing.image_score is None
    assert isinstance(listing.image_scored_at, datetime)


def test_score_listing_image_invalid_url_scheme(monkeypatch):
    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("should not fetch a non-http(s) url")

    monkeypatch.setattr(image_scorer.httpx, "get", _fail_if_called)

    listing = _listing(image_url="ftp://example.com/photo.jpg")
    score_listing_image(listing)

    assert listing.image_score is None


def test_score_listing_image_fetch_non_200(monkeypatch):
    monkeypatch.setattr(image_scorer.httpx, "get", lambda *a, **kw: _fake_response(status_code=404))

    listing = _listing()
    score_listing_image(listing)

    assert listing.image_score is None


def test_score_listing_image_fetch_raises(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(image_scorer.httpx, "get", _raise)

    listing = _listing()
    score_listing_image(listing)

    assert listing.image_score is None
    assert isinstance(listing.image_scored_at, datetime)


def test_score_listing_image_success(monkeypatch):
    monkeypatch.setattr(image_scorer.httpx, "get", lambda *a, **kw: _fake_response())
    monkeypatch.setattr(
        image_scorer._client.messages,
        "create",
        lambda **kw: _fake_anthropic_result('{"score": 12, "reason": "Lumineux et propre"}'),
    )

    listing = _listing()
    score_listing_image(listing)

    assert listing.image_score == 12.0


def test_score_listing_image_strips_markdown_fences(monkeypatch):
    monkeypatch.setattr(image_scorer.httpx, "get", lambda *a, **kw: _fake_response())
    monkeypatch.setattr(
        image_scorer._client.messages,
        "create",
        lambda **kw: _fake_anthropic_result('```json\n{"score": 8, "reason": "Correct"}\n```'),
    )

    listing = _listing()
    score_listing_image(listing)

    assert listing.image_score == 8.0


def test_score_listing_image_non_json_response(monkeypatch):
    monkeypatch.setattr(image_scorer.httpx, "get", lambda *a, **kw: _fake_response())
    monkeypatch.setattr(
        image_scorer._client.messages,
        "create",
        lambda **kw: _fake_anthropic_result("Je ne peux pas évaluer cette image."),
    )

    listing = _listing()
    score_listing_image(listing)

    assert listing.image_score is None


def test_score_listing_image_non_text_block(monkeypatch):
    monkeypatch.setattr(image_scorer.httpx, "get", lambda *a, **kw: _fake_response())
    monkeypatch.setattr(
        image_scorer._client.messages,
        "create",
        lambda **kw: SimpleNamespace(content=[SimpleNamespace(type="tool_use")]),
    )

    listing = _listing()
    score_listing_image(listing)

    assert listing.image_score is None


def test_score_listing_image_unsupported_content_type_falls_back_to_jpeg(monkeypatch):
    captured = {}

    def _fake_create(**kwargs):
        captured["media_type"] = kwargs["messages"][0]["content"][0]["source"]["media_type"]
        return _fake_anthropic_result('{"score": 5, "reason": "ok"}')

    monkeypatch.setattr(
        image_scorer.httpx, "get", lambda *a, **kw: _fake_response(content_type="text/html")
    )
    monkeypatch.setattr(image_scorer._client.messages, "create", _fake_create)

    listing = _listing()
    score_listing_image(listing)

    assert captured["media_type"] == "image/jpeg"
    assert listing.image_score == 5.0
