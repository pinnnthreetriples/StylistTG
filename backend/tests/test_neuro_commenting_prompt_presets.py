from __future__ import annotations

from app.services.neuro_commenting.prompt_presets import (
    get_prompt_preset,
    list_prompt_presets,
)


def test_prompt_presets_catalogue_has_required_ids() -> None:
    catalogue = list_prompt_presets()
    ids = {preset.id for preset in catalogue}

    assert {
        "short_native_ru",
        "expert_opinion_ru",
        "question_to_author_ru",
        "emoji_reaction_ru",
        "short_native_en",
    }.issubset(ids)


def test_prompt_presets_have_non_empty_text_fields() -> None:
    for preset in list_prompt_presets():
        assert preset.name.strip()
        assert preset.description.strip()
        assert preset.system_prompt.strip()
        assert preset.prompt_template.strip()
        assert preset.language in {"ru", "en"}


def test_get_prompt_preset_unknown_returns_none() -> None:
    assert get_prompt_preset("does_not_exist") is None


def test_get_prompt_preset_known_returns_payload() -> None:
    preset = get_prompt_preset("short_native_ru")

    assert preset is not None
    assert preset.language == "ru"
    assert "3" in preset.description  # mentions 3-7 words range


def test_prompt_presets_endpoint_returns_catalogue(app_client) -> None:
    response = app_client.get("/api/neuro-commenting/prompt-presets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == len(list_prompt_presets())
    assert {item["id"] for item in payload["items"]} >= {"short_native_ru", "emoji_reaction_ru"}
