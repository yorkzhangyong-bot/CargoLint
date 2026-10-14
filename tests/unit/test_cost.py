"""Token cost from the price table, EUR conversion, accumulation and reset (FR-040)."""
from pathlib import Path

import pytest

from agent.llm import UnknownModelError, compute_cost, load_prices, usage_from_tokens
from agent.schemas import Usage

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def prices():
    return load_prices(ROOT / "data" / "model_prices.json")


def test_price_table_loads_with_date(prices):
    assert prices.as_of == "2026-10-14"
    assert "openai/gpt-4o-mini" in prices.models


def test_cost_from_tokens_in_usd_and_eur(prices):
    usd, eur = compute_cost("openai/gpt-4o-mini", 1_000_000, 1_000_000, prices, usd_eur=0.92)
    assert usd == pytest.approx(0.75)
    assert eur == pytest.approx(0.69)
    usd2, _ = compute_cost("qwen/qwen3-embedding-8b", 2_000_000, 0, prices, usd_eur=0.92)
    assert usd2 == pytest.approx(0.02)


def test_unknown_model_raises(prices):
    with pytest.raises(UnknownModelError):
        compute_cost("vendor/unknown-model", 10, 10, prices, usd_eur=0.92)


def test_usage_from_tokens_builds_a_usage_record(prices):
    u = usage_from_tokens("openai/gpt-4o-mini", 1000, 500, prices, usd_eur=0.92)
    assert isinstance(u, Usage)
    assert u.prompt_tokens == 1000 and u.completion_tokens == 500 and u.total_tokens == 1500 and u.calls == 1
    assert u.cost_usd == pytest.approx(0.00015 + 0.0003)
    assert u.cost_eur == pytest.approx(u.cost_usd * 0.92)


def test_usage_accumulates_and_store_resets(memory_store):
    total = Usage()
    part = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.01, cost_eur=0.0092, calls=1)
    total.add(part)
    total.add(part)
    assert total.total_tokens == 300 and total.calls == 2 and total.cost_eur == pytest.approx(0.0184)
    memory_store.add_usage(part)
    memory_store.add_usage(part)
    assert memory_store.shipment.usage.total_tokens == 300
    memory_store.new_shipment(reference="X", threshold=85)
    assert memory_store.shipment.usage.calls == 0
