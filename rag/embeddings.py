"""Embeddings: OpenRouter's /embeddings endpoint through the OpenAI SDK, plus a deterministic
fake for offline tests (research.md R-03)."""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from typing import Any

from langchain_core.embeddings import Embeddings

from agent.config import OPENROUTER_BASE_URL, Settings, get_settings
from agent.schemas import Usage

_TOKEN_RE = re.compile(r"[0-9]{4}\.[0-9]{2}|[a-z0-9]+|[一-鿿]")


class FakeEmbeddings(Embeddings):
    """Hashed bag-of-words vectors: deterministic, offline, similar texts get similar vectors."""

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim
        self.model_id = f"fake-hash-{dim}"

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _TOKEN_RE.findall(text.lower()):
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            v[h % self.dim] += 1.0
            v[(h >> 8) % self.dim] += 0.5
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class OpenRouterEmbeddings(Embeddings):
    """POST /api/v1/embeddings with `input_type` and provider pinning; records usage.cost."""

    def __init__(
        self,
        settings: Settings | None = None,
        model: str | None = None,
        batch_size: int = 64,
        provider_order: list[str] | None = None,
        usage_sink: Callable[[Usage], None] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if not self.settings.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (environment or .env)")
        self.model_id = model or self.settings.embed_model
        self.batch_size = batch_size
        self.provider_order = provider_order
        self.usage_sink = usage_sink
        self.dimension: int | None = None
        from openai import OpenAI

        headers = {"X-OpenRouter-Title": self.settings.app_title}
        if self.settings.http_referer:
            headers["HTTP-Referer"] = self.settings.http_referer
        self._client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=self.settings.api_key, default_headers=headers, max_retries=3)

    def _call(self, texts: list[str], input_type: str) -> list[list[float]]:
        extra: dict[str, Any] = {"input_type": input_type}
        if self.provider_order:
            extra["provider"] = {"order": self.provider_order, "allow_fallbacks": False}
        resp = self._client.embeddings.create(model=self.model_id, input=texts, encoding_format="float", extra_body=extra)
        vectors = [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        if vectors:
            self.dimension = len(vectors[0])
        usage = getattr(resp, "usage", None)
        if self.usage_sink is not None and usage is not None:
            prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
            cost = float(getattr(usage, "cost", 0.0) or 0.0)
            self.usage_sink(Usage(prompt_tokens=prompt, total_tokens=int(getattr(usage, "total_tokens", prompt) or prompt),
                                  cost_usd=cost, cost_eur=cost * self.settings.usd_eur, calls=1))
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._call(texts[i:i + self.batch_size], "search_document"))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._call([text], "search_query")[0]


def get_embeddings(settings: Settings | None = None, usage_sink: Callable[[Usage], None] | None = None) -> Embeddings:
    return OpenRouterEmbeddings(settings=settings, usage_sink=usage_sink)
