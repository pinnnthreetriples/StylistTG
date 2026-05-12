"""Extended tests for app.adapters.warmup_text_provider.

Covers UnavailableWarmupTextProvider, _pick, _apply_light_variation,
and edge cases not hit by the existing test_warmup_providers.py.
"""

from __future__ import annotations

from app.adapters.warmup_text_provider import (
    MockWarmupTextProvider,
    TextVariationRequest,
    UnavailableWarmupTextProvider,
    _apply_light_variation,
    _pick,
    build_warmup_text_provider,
)


# ---------------------------------------------------------------------------
# _pick
# ---------------------------------------------------------------------------


def test_pick_deterministic():
    items = ("a", "b", "c", "d", "e")
    assert _pick(items, "seed1") == _pick(items, "seed1")


def test_pick_different_seeds_may_differ():
    items = ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j")
    results = {_pick(items, f"seed-{i}") for i in range(50)}
    assert len(results) > 1


def test_pick_single_item():
    assert _pick(("only",), "any_seed") == "only"


# ---------------------------------------------------------------------------
# _apply_light_variation
# ---------------------------------------------------------------------------


def test_light_variation_deterministic():
    a = _apply_light_variation("Hello world!", "seed-42")
    b = _apply_light_variation("Hello world!", "seed-42")
    assert a == b


def test_light_variation_strips_existing_punctuation():
    result = _apply_light_variation("Hello...", "seed-1")
    assert not result.endswith("...")  # original ... should be replaced


def test_light_variation_empty_string():
    assert _apply_light_variation("", "seed") == ""
    assert _apply_light_variation("   ", "seed") == ""


def test_light_variation_all_variants_covered():
    text = "Hello world"
    variants = set()
    for i in range(100):
        result = _apply_light_variation(text, f"seed-{i}")
        if result.endswith("."):
            variants.add("dot")
        elif result.endswith("…"):
            variants.add("ellipsis")
        elif result.endswith("!"):
            variants.add("excl")
        else:
            variants.add("bare")
    assert len(variants) >= 3


# ---------------------------------------------------------------------------
# UnavailableWarmupTextProvider
# ---------------------------------------------------------------------------


def test_unavailable_provider_not_available():
    provider = UnavailableWarmupTextProvider()
    assert provider.is_available() is False
    assert provider.provider_name == "unavailable"


def test_unavailable_provider_generate_bio():
    provider = UnavailableWarmupTextProvider()
    result = provider.generate_bio(seed="s1")
    assert result.rendered == ""
    assert result.provider == "unavailable"


def test_unavailable_provider_rewrite_text():
    provider = UnavailableWarmupTextProvider()
    req = TextVariationRequest(template="Hello", seed="s1")
    result = provider.rewrite_text(req)
    assert result.rendered == ""


def test_unavailable_provider_compose_p2p_message():
    provider = UnavailableWarmupTextProvider()
    req = TextVariationRequest(template="", seed="s1")
    result = provider.compose_p2p_message(req)
    assert result.rendered == ""


def test_unavailable_provider_compose_spam_bot_reply():
    provider = UnavailableWarmupTextProvider()
    req = TextVariationRequest(template="", seed="s1")
    result = provider.compose_spam_bot_reply(req)
    assert result.rendered == ""


# ---------------------------------------------------------------------------
# MockWarmupTextProvider edge cases
# ---------------------------------------------------------------------------


def test_mock_provider_rewrite_preserves_meaning():
    provider = MockWarmupTextProvider()
    req = TextVariationRequest(template="Test message.", seed="seed-1")
    result = provider.rewrite_text(req)
    assert "Test message" in result.rendered or "Test" in result.rendered


def test_mock_provider_generate_bio_locale_param():
    provider = MockWarmupTextProvider()
    result = provider.generate_bio(seed="bio-seed", locale="en")
    assert result.rendered  # still works with non-default locale


def test_mock_provider_compose_p2p_with_template():
    provider = MockWarmupTextProvider()
    req = TextVariationRequest(template="Custom text", seed="pair-1")
    result = provider.compose_p2p_message(req)
    assert result.template == "Custom text"
    assert result.rendered  # applied light variation


def test_mock_provider_compose_spam_bot_with_template():
    provider = MockWarmupTextProvider()
    req = TextVariationRequest(template="Custom reply.", seed="spam-1")
    result = provider.compose_spam_bot_reply(req)
    assert result.rendered == "Custom reply."


# ---------------------------------------------------------------------------
# build_warmup_text_provider
# ---------------------------------------------------------------------------


def test_build_returns_mock():
    provider = build_warmup_text_provider()
    assert provider.provider_name == "mock"
    assert provider.is_available() is True
