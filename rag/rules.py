"""Rule lists (firm stop-words, the two ICS2 lists, bilingual aliases), deterministic matching,
the pure-stop-word test and shipper profiles (FR-007 … FR-011, FR-016, FR-042)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from agent.config import RULES_DIR, DATA_DIR
from agent.schemas import Alias, FlagKind, RuleEntry, RuleList, RuleSource, ShipperProfile

ASK_FOR_DEFAULT = ["material", "product_name", "use"]
_CJK = re.compile(r"[一-鿿]")
_LATIN_WORD = re.compile(r"[a-z0-9]")


@dataclass
class RuleMatch:
    kind: FlagKind
    rule_source: RuleSource
    matched_term: str
    list_name: str
    source_doc: str
    source_date: str
    ask_for: list[str] = field(default_factory=lambda: list(ASK_FOR_DEFAULT))
    reason: str = ""


def default_ask_for(kind: FlagKind | str) -> list[str]:
    return [] if FlagKind(kind) == FlagKind.ok else list(ASK_FOR_DEFAULT)


def _word_match(text_lower: str, term_lower: str) -> bool:
    """Whole-term, case-insensitive match for Latin terms ('gift' does not match 'gifted')."""
    pattern = r"(?<![a-z0-9])" + re.escape(term_lower) + r"(?![a-z0-9])"
    return re.search(pattern, text_lower) is not None


def _term_matches(text_zh: str, text_en: str, term: str, lang: str) -> bool:
    if lang == "zh" or _CJK.search(term):
        return term in text_zh or term in text_en
    t = term.lower()
    return _word_match(text_en.lower(), t) or _word_match(text_zh.lower(), t)


class RuleSet:
    def __init__(self, firm: RuleList, ics2_lists: list[RuleList], aliases: list[Alias]) -> None:
        self.firm = firm
        self.ics2_lists = ics2_lists
        self.aliases = aliases

    @classmethod
    def load(cls, rules_dir: Path | str | None = None) -> "RuleSet":
        d = Path(rules_dir or RULES_DIR)
        firm = RuleList.model_validate(json.loads((d / "firm_stop_words.json").read_text(encoding="utf-8")))
        ics2: list[RuleList] = []
        for name in ("ics2_unacceptable_terms.json", "ics2_stop_words.json"):
            p = d / name
            if p.exists():
                ics2.append(RuleList.model_validate(json.loads(p.read_text(encoding="utf-8"))))
        aliases: list[Alias] = []
        p = d / "ics2_aliases.json"
        if p.exists():
            aliases = [Alias.model_validate(e) for e in json.loads(p.read_text(encoding="utf-8")).get("entries", [])]
        return cls(firm, ics2, aliases)

    def caption_facts(self) -> dict:
        return {
            "firm_terms": len(self.firm.entries),
            "ics2_terms": sum(len(l.entries) for l in self.ics2_lists),
            "ics2_docs": [{"list": l.list, "source_doc": l.source_doc, "source_date": l.source_date, "terms": len(l.entries)}
                          for l in self.ics2_lists],
            "firm_source": self.firm.source_doc,
        }

    def ics2_list_for(self, term: str) -> RuleList | None:
        t = term.lower()
        for rl in self.ics2_lists:
            if any(e.term.lower() == t for e in rl.entries):
                return rl
        return self.ics2_lists[0] if self.ics2_lists else None


def _source_for(list_name: str) -> RuleSource:
    return {"firm_stop_words": RuleSource.firm_stop_words, "ics2_unacceptable": RuleSource.ics2_unacceptable,
            "ics2_stop_words": RuleSource.ics2_stop_words}.get(list_name, RuleSource.ics2_unacceptable)


def check_rules(text_zh: str, text_en: str, rules: RuleSet) -> RuleMatch | None:
    """Deterministic rule match: firm list first (Stop-word), then the ICS2 lists and the bilingual
    aliases (Vague). Returns None when no rule matches (judgement follows in the tool)."""
    text_zh = text_zh or ""
    text_en = text_en or ""
    # 1. firm stop-words → Stop-word (precedence)
    for e in sorted(rules.firm.entries, key=lambda e: -len(e.term)):
        if _term_matches(text_zh, text_en, e.term, e.lang):
            return RuleMatch(kind=FlagKind.stop_word, rule_source=RuleSource.firm_stop_words, matched_term=e.term,
                             list_name=rules.firm.list, source_doc=rules.firm.source_doc, source_date=rules.firm.source_date,
                             reason=f"\"{e.term}\" is on the firm stop-word list")
    # 2. ICS2 lists → Vague
    for rl in rules.ics2_lists:
        for e in sorted(rl.entries, key=lambda e: -len(e.term)):
            if _term_matches(text_zh, text_en, e.term, e.lang):
                return RuleMatch(kind=FlagKind.vague, rule_source=_source_for(rl.list), matched_term=e.term.lower(),
                                 list_name=rl.list, source_doc=rl.source_doc, source_date=rl.source_date,
                                 reason=f"\"{e.term}\" is listed by ICS2 as an unacceptable goods description")
    # 3. aliases (Chinese and English variants) → canonical ICS2 term
    for a in sorted(rules.aliases, key=lambda a: -len(a.alias)):
        if _term_matches(text_zh, text_en, a.alias, a.lang):
            rl = rules.ics2_list_for(a.term)
            if rl is None:
                continue
            return RuleMatch(kind=FlagKind.vague, rule_source=_source_for(rl.list), matched_term=a.term.lower(),
                             list_name=rl.list, source_doc=rl.source_doc, source_date=rl.source_date,
                             reason=f"\"{a.alias}\" means \"{a.term}\", which ICS2 lists as an unacceptable goods description")
    return None


def is_pure_stop_word(text_zh: str, text_en: str, match: RuleMatch | None, rules: RuleSet) -> bool:
    """True when nothing but stop-word terms (and punctuation) remains in the description."""
    if match is None or match.kind != FlagKind.stop_word:
        return False
    rest_zh, rest_en = (text_zh or ""), (text_en or "")
    for e in rules.firm.entries:
        if e.lang == "zh" or _CJK.search(e.term):
            rest_zh = rest_zh.replace(e.term, " ")
            rest_en = rest_en.replace(e.term, " ")
        else:
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(e.term) + r"(?![a-z0-9])", re.I)
            rest_en = pat.sub(" ", rest_en)
            rest_zh = pat.sub(" ", rest_zh)
    remaining = rest_zh + " " + rest_en
    letters = len(_LATIN_WORD.findall(remaining.lower())) + len(_CJK.findall(remaining))
    return letters < 2


# --------------------------------------------------------------------------- shippers
def load_shippers(path: Path | str | None = None) -> list[ShipperProfile]:
    p = Path(path or (DATA_DIR / "shippers.json"))
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [ShipperProfile.model_validate(s) for s in data.get("shippers", [])]


def detect_shipper(texts: Iterable[str], shippers: list[ShipperProfile]) -> ShipperProfile | None:
    joined = " ".join(str(t) for t in texts if t).lower()
    if not joined.strip():
        return None
    for s in shippers:
        for name in [s.name, *s.aliases]:
            if name and name.lower() in joined:
                return s
    return None


def find_shipper(name: str | None, shippers: list[ShipperProfile]) -> ShipperProfile | None:
    if not name:
        return None
    n = name.lower()
    for s in shippers:
        if s.name.lower() == n or n in (a.lower() for a in s.aliases):
            return s
    return None
