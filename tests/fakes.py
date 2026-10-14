"""Test doubles shared by the offline test suite.

`FakeRawClient` stands in for the raw structured-output backend used by
`agent.llm.StructuredCaller`: it returns recorded outputs keyed by the schema
name and the fenced input text, can be told to raise for chosen inputs (per-line
isolation tests) and to return invalid output a number of times (schema retry
tests). Every call is logged so tests can assert what reached the "model".
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_RE = re.compile(r"<data[^>]*>(.*?)</data>", re.S)


class FakeRawClient:
    def __init__(
        self,
        recorded: dict[str, dict[str, Any]] | None = None,
        fail_on: set[str] | None = None,
        invalid_first: dict[str, int] | None = None,
    ) -> None:
        self.recorded = recorded or {}
        self.fail_on = set(fail_on or ())
        self.invalid_first = dict(invalid_first or {})
        self.calls: list[dict[str, Any]] = []
        self.last_usage: dict[str, int] = {}

    @classmethod
    def from_dir(cls, path: Path) -> "FakeRawClient":
        recorded: dict[str, dict[str, Any]] = {}
        for file in sorted(Path(path).glob("*.json")):
            recorded[file.stem] = json.loads(file.read_text(encoding="utf-8"))
        return cls(recorded=recorded)

    @staticmethod
    def key_for(user: str) -> str:
        found = DATA_RE.findall(user)
        if found:
            return found[0].strip()
        return user.strip()

    def raw_structured(self, schema: type, system: str, user: str) -> dict[str, Any]:
        key = self.key_for(user)
        self.calls.append({"schema": schema.__name__, "system": system, "user": user, "key": key})
        self.last_usage = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
        if key in self.fail_on:
            raise RuntimeError(f"simulated model failure for {key!r}")
        remaining = self.invalid_first.get(key, 0)
        if remaining > 0:
            self.invalid_first[key] = remaining - 1
            return {"garbage": True, "candidates": "not-a-list"}
        table = self.recorded.get(schema.__name__, {})
        if key in table:
            return table[key]
        return self.default_for(schema, key)

    @staticmethod
    def default_for(schema: type, key: str) -> dict[str, Any]:
        name = schema.__name__
        if name == "JudgementOut":
            return {"vague": True, "missing": ["material", "product_name", "use"], "reason": "no recorded judgement"}
        if name == "TranslateOut":
            return {"queries": [key or "unknown goods"], "hyde": None}
        if name == "RankOut":
            return {"candidates": []}
        if name == "ExtractOut":
            return {"material": "", "part_name": "", "use": ""}
        return {}

    # Convenience for assertions -------------------------------------------------
    def prompts_for(self, schema_name: str) -> list[str]:
        return [c["user"] for c in self.calls if c["schema"] == schema_name]
