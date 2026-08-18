from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.constants import ModelTier
from app.orchestrator.llm_clients import resolve_model_for_tier


def test_resolve_model_for_tier_uses_correct_settings():
    # Provide explicit settings so we aren't dependent on the environment.
    settings = Settings(
        MODEL_CHEAP="claude-3-5-haiku-20241022",
        MODEL_PROVIDER_CHEAP="anthropic",
        MODEL_CODING="claude-3-5-sonnet-20241022",
        MODEL_PROVIDER_CODING="anthropic",
        MODEL_REASONING="claude-3-5-sonnet-20241022",
        MODEL_PROVIDER_REASONING="anthropic",
        MODEL_FALLBACK="claude-3-5-haiku-20241022",
        MODEL_PROVIDER_FALLBACK="anthropic",
    )

    # Test Cheap tier -> Haiku
    model, provider = resolve_model_for_tier(ModelTier.CHEAP, settings)
    assert model == "claude-3-5-haiku-20241022"
    assert provider == "anthropic"

    # Test Coding tier -> Sonnet
    model, provider = resolve_model_for_tier(ModelTier.CODING, settings)
    assert model == "claude-3-5-sonnet-20241022"
    assert provider == "anthropic"

    # Test Reasoning tier (complex planning) -> Sonnet
    model, provider = resolve_model_for_tier(ModelTier.REASONING, settings)
    assert model == "claude-3-5-sonnet-20241022"
    assert provider == "anthropic"

    # Test Fallback tier -> Haiku
    model, provider = resolve_model_for_tier(ModelTier.FALLBACK, settings)
    assert model == "claude-3-5-haiku-20241022"
    assert provider == "anthropic"


def test_resolve_model_for_tier_raises_for_deterministic():
    settings = Settings()
    with pytest.raises(ValueError, match="is DETERMINISTIC"):
        resolve_model_for_tier(ModelTier.DETERMINISTIC, settings)
