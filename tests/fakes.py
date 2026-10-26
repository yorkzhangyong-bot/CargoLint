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

KEY_RE = re.compile(r"<(goods|data)[^>]*>(.*?)</\1>", re.S)   # the CN-8 request fences its goods text as <goods>


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
        self.not_json_first: dict[tuple[str, str], int] = {}   # (schema, key) -> answers that are not JSON at all
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
        found = KEY_RE.findall(user)
        if found:
            return found[0][1].strip()
        return user.strip()

    def raw_structured(self, schema: type, system: str, user: str) -> dict[str, Any]:
        key = self.key_for(user)
        self.calls.append({"schema": schema.__name__, "system": system, "user": user, "key": key})
        self.last_usage = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
        if key in self.fail_on:
            raise RuntimeError(f"simulated model failure for {key!r}")
        scoped = (schema.__name__, key)
        if self.not_json_first.get(scoped, 0) > 0:   # what OpenRouterRawClient returns for a text that is not JSON
            self.not_json_first[scoped] -= 1
            return {"_invalid": True, "content": "Sure! The best subheading is 9617.00."}
        k = scoped if scoped in self.invalid_first else key
        remaining = self.invalid_first.get(k, 0)
        if remaining > 0:
            self.invalid_first[k] = remaining - 1
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
        if name == "Cn8Out":  # an unrecorded line gets a question, never a written CN-8
            return {"cn8": None, "confidence": 0, "deciding_attribute": "the attribute that separates the CN-8 lines",
                    "attribute_visible": False, "evidence": "", "rationale": "no recorded CN-8 judgement", "precedent": None}
        if name == "SubdivisionOut":
            return {"code": None, "confidence": 0, "attribute_visible": False, "rationale": "no recorded judgement"}
        return {}

    # Convenience for assertions -------------------------------------------------
    def prompts_for(self, schema_name: str) -> list[str]:
        return [c["user"] for c in self.calls if c["schema"] == schema_name]


# --------------------------------------------------------------------------- scripted chat model for the agent loop
from typing import Any as _Any  # noqa: E402

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402


def ai_tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


class ScriptedChatModel(BaseChatModel):
    """Returns the scripted AIMessages in order; tool binding is accepted and ignored."""

    responses: list[AIMessage]
    cursor: int = 0
    seen: list[list[_Any]] = []

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        if self.cursor >= len(self.responses):
            msg = AIMessage(content="(script exhausted)")
        else:
            msg = self.responses[self.cursor]
            self.cursor += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _llm_type(self) -> str:
        return "scripted"


def assert_no_unconfirmed_writes(store) -> None:
    """SC-005 (feature 004): nothing is written without the clerk's confirmation where a rule requires it."""
    threshold = store.shipment.threshold
    for line in store.lines:
        c = line.current.cn8
        cn8_written = c is not None and c.cn8 is not None and c.written_by is not None
        if cn8_written:
            assert c.cn8 in [code for code, _ in c.options], f"line {line.line_no}: written CN-8 {c.cn8} is not one of its options"
            if c.written_by.value == "rule":
                assert len(c.options) == 1 or c.confidence >= threshold, f"line {line.line_no}: CN-8 written below the threshold"
                assert len(c.options) == 1 or not (c.precedent and c.precedent.code[:8] != c.cn8), \
                    f"line {line.line_no}: CN-8 written although its cited ruling is at another CN-8"
        t = line.current.taric
        if t is None or t.taric10 is None or t.written_by is None:
            continue
        assert t.taric10 in t.subdivisions, f"line {line.line_no}: written TARIC-10 {t.taric10} is not one of its subdivisions"
        if t.written_by.value == "rule":
            assert len(t.subdivisions) == 1, f"line {line.line_no}: TARIC-10 written by rule among several subdivisions"
            assert t.rule.value == "auto_completed" and not t.trade_defence, \
                f"line {line.line_no}: TARIC-10 written by rule although a confirm type applies"
            assert cn8_written, f"line {line.line_no}: TARIC-10 written by rule while its CN-8 is not written"
