"""Live checks against OpenRouter (need OPENROUTER_API_KEY; spend a fraction of a cent).

Covers research.md R-02/R-03/R-06: the embeddings endpoint, strict structured output with the default
chat model, and the price-table cost against OpenRouter's own accounting.
"""
import time

import pytest

from agent.config import get_settings
from agent.llm import OpenRouterRawClient, StructuredCaller, compute_cost, load_prices
from agent.schemas import RankOut, Usage
from rag.embeddings import OpenRouterEmbeddings

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def settings():
    return get_settings()


def test_embeddings_endpoint_returns_vectors_for_chinese_and_english(settings):
    usage = Usage()
    emb = OpenRouterEmbeddings(settings=settings, usage_sink=usage.add)
    vectors = emb.embed_documents(["不锈钢保温杯 500ml", "Stainless steel vacuum flask, 500 ml"])
    assert len(vectors) == 2 and len(vectors[0]) == len(vectors[1]) > 100
    assert emb.dimension == len(vectors[0])
    q = emb.embed_query("vacuum flask")
    assert len(q) == emb.dimension
    assert usage.calls == 2 and usage.prompt_tokens > 0


def test_structured_output_with_the_default_model(settings):
    usage = Usage()
    raw = OpenRouterRawClient(settings)
    caller = StructuredCaller(raw=raw, model_name=settings.chat_model, prices=load_prices(), usd_eur=settings.usd_eur, usage_sink=usage.add)
    out = caller.call(
        RankOut,
        "Rank HS-6 candidates for the goods. Use only codes from the list. Return JSON {candidates:[{code, confidence, rationale, history_only}]}.",
        'Goods: <data line="1">Stainless steel vacuum flask, 500 ml</data>\nCandidates: [hs:9617.00] Vacuum flasks and other vacuum vessels; '
        "[hs:3924.10] Tableware and kitchenware of plastics; [hs:7323.93] Table, kitchen or other household articles of stainless steel",
    )
    assert out.candidates and out.candidates[0].code == "9617.00"
    assert 0 <= out.candidates[0].confidence <= 100
    assert usage.calls == 1 and usage.total_tokens > 0 and usage.cost_eur > 0


def test_price_table_cost_matches_openrouter_accounting_within_tolerance(settings):
    from openai import OpenAI
    import requests

    from agent.config import OPENROUTER_BASE_URL

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=settings.api_key)
    resp = client.chat.completions.create(model=settings.chat_model, messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                                          max_tokens=5, temperature=0)
    usage = resp.usage
    ours_usd, _ = compute_cost(settings.chat_model, usage.prompt_tokens, usage.completion_tokens, load_prices(), settings.usd_eur)
    reported = getattr(usage, "cost", None)
    if reported is None:
        for _ in range(6):  # the generation record can lag a few seconds
            r = requests.get(f"{OPENROUTER_BASE_URL}/generation", params={"id": resp.id}, headers={"Authorization": f"Bearer {settings.api_key}"}, timeout=30)
            if r.status_code == 200 and r.json().get("data", {}).get("total_cost") is not None:
                reported = float(r.json()["data"]["total_cost"])
                break
            time.sleep(2)
    assert reported is not None, "no cost reported by OpenRouter"
    if reported == 0:
        assert ours_usd < 0.001
    else:
        assert abs(ours_usd - reported) / reported <= 0.10, f"price table {ours_usd:.6f} vs OpenRouter {reported:.6f}"
