"""Pricing table tests (app/orchestrator/pricing.py)."""
from __future__ import annotations

from app.orchestrator.pricing import calculate_cost, get_price, provider_for_model


def test_known_model_uses_its_configured_price():
    price = get_price("gpt-4o-mini")
    assert price["provider"] == "openai"
    assert price["input_per_1k"] > 0


def test_unknown_model_falls_back_rather_than_crashing():
    price = get_price("some-made-up-model-name")
    assert "input_per_1k" in price
    assert "output_per_1k" in price


def test_cost_calculation_is_proportional_to_tokens():
    cost_1k = calculate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=0)
    cost_2k = calculate_cost("gpt-4o-mini", input_tokens=2000, output_tokens=0)
    assert cost_2k == round(cost_1k * 2, 6)


def test_zero_tokens_costs_nothing():
    assert calculate_cost("gpt-4o-mini", input_tokens=0, output_tokens=0) == 0.0


def test_provider_for_model_matches_pricing_table():
    assert provider_for_model("claude-sonnet-5") == "anthropic"
    assert provider_for_model("gpt-4o") == "openai"
