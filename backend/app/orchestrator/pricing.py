"""
Cost calculation from a small, editable pricing table.

Prices are intentionally NOT hardcoded as Python constants: they live in
pricing_table.json (same directory) so an operator can update them without
a code change or redeploy, and so the numbers in this repo are visibly
"example data to edit" rather than presented as a live, authoritative
price feed. See docs/16 in the original brief / docs/23-design-decisions.md.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DEFAULT_TABLE_PATH = Path(__file__).parent / "pricing_table.json"

_FALLBACK_PRICE = {"input_per_1k": 0.003, "output_per_1k": 0.015, "provider": "unknown"}


@lru_cache
def _load_table(path: str | None = None) -> dict:
    table_path = Path(path) if path else _DEFAULT_TABLE_PATH
    try:
        with open(table_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_price(model: str, table_path: str | None = None) -> dict:
    table = _load_table(table_path)
    return table.get(model, _FALLBACK_PRICE)


def calculate_cost(model: str, input_tokens: int, output_tokens: int, table_path: str | None = None) -> float:
    price = get_price(model, table_path)
    cost = (input_tokens / 1000.0) * price["input_per_1k"] + (output_tokens / 1000.0) * price["output_per_1k"]
    return round(cost, 6)


def provider_for_model(model: str, table_path: str | None = None) -> str:
    return get_price(model, table_path).get("provider", "unknown")
