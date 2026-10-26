"""Rule lists (firm stop-words, the two ICS2 lists, bilingual aliases), deterministic matching on the goods name
(feature 007), the pure-stop-word test and shipper profiles (FR-007 … FR-011, FR-016, FR-042)."""
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


class RuleSet:
    def __init__(self, firm: RuleList, ics2_lists: list[RuleList], aliases: list[Alias]) -> None:
        self.firm = firm
        self.ics2_lists = ics2_lists
        self.aliases = aliases
        self.terms = _terms(self)

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
        return None  # an alias may only cite a term that is really on an ICS2 list


def _source_for(list_name: str) -> RuleSource:
    return {"firm_stop_words": RuleSource.firm_stop_words, "ics2_unacceptable": RuleSource.ics2_unacceptable,
            "ics2_stop_words": RuleSource.ics2_stop_words}.get(list_name, RuleSource.ics2_unacceptable)


# --------------------------------------------------------------------------- matching on the goods name (feature 007)
# A listed term locks a line only when the goods name is nothing but listed terms and filler words. ICS2 rejects a
# general term used as the description ("Parts", "Various goods"), not one that sits in a property ("T-shirts in
# various sizes") or that the goods name qualifies: the DG TAXUD guidance accepts "Poultry equipment" and "Lighting and
# electrical accessories". The rule is the same for every list, with no exception: the guidance gives the firm list's
# catch-alls ("various", "personal effects", "gifts") as general terms too, and its fixed phrases ("gift box", "machine
# parts", "auto parts", "various goods") are listed terms of their own, so they still lock a goods name that is nothing
# else. One point is looser than the guidance's examples: for parts it names the part itself ("Pump, Seals, Engines"),
# while "spare parts for pumps" passes here and is left to the model's judgement, which follows every unflagged line.
_NAME_END = re.compile(
    r"[,;:!?()\[\]{}\r\n，；：。！？（）【】、]|\.(?=\s|$)|\s[-–—]\s"
    r"|(?:^|\s)(?:in|with|made|available|including|which|that|as|at|from)(?=\s)", re.I)
_WORD = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
CJK_FILLER = ("其他", "其它", "各类", "货物", "产品", "物品", "商品", "用品", "套装", "尺寸", "颜色", "规格", "型号", "款式",
              "的", "和", "及", "与", "等", "类")


def goods_name(text: str) -> str:
    """The goods name: the description's leading phrase, up to the first punctuation mark (a full stop, not a decimal
    point), spaced dash or word that opens a property ("in various sizes", "made from", "available in", "that vary").
    Empty when the description opens with a property."""
    text = (text or "").strip()
    end = _NAME_END.search(text)
    return (text[:end.start()] if end else text).strip()


def _singular(word: str) -> str:
    """One form for both numbers, as the ICS2 stop-word list uses them interchangeably ("parts" and "part", "boxes" and
    "box", "accessories" and "accessory")."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("sses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [_singular(w) for w in _WORD.findall((text or "").lower())]


FILLER = {_singular(w) for w in (
    "of", "for", "and", "or", "the", "a", "an", "in", "with", "to", "on", "by", "per", "various", "misc", "etc",
    "products", "product", "goods", "items", "item", "articles", "article", "general", "all", "kind", "kinds", "type",
    "types", "sort", "other", "others", "assorted", "mixed", "pcs", "pc", "ctn", "ctns", "set", "sets", "pair", "unit",
    "dozen", "qty", "kg", "mm", "cm", "ml", "new", "used", "size", "colour", "color", "style", "model", "shape", "design")}


@dataclass(frozen=True)
class _Term:
    """A listed term (or an alias of one) and what a flag on it cites."""

    text: str                     # what is looked for
    words: tuple[str, ...]        # its words, one form for both numbers; empty for a Chinese term
    kind: FlagKind
    rule_list: RuleList
    matched_term: str
    reason: str


def _terms(rules: RuleSet) -> list[_Term]:
    """Every term in the order the lists take precedence: the firm list (Stop-word), the two ICS2 lists, then the
    aliases of their terms (Vague); within a list the longest first, so "spare parts" before "parts", and of two forms
    of one term the list's shorter ("gift" before "gifts")."""
    def ordered(items: list[tuple[str, _Term]]) -> list[_Term]:
        return [t for _, t in sorted(items, key=lambda it: (-len(" ".join(it[1].words) or it[1].text), len(it[0])))]

    def term(text: str, kind: FlagKind, rl: RuleList, shown: str, reason: str) -> tuple[str, _Term]:
        words = () if _CJK.search(text) else tuple(_words(text))
        return text, _Term(text, words, kind, rl, shown, reason)

    out = ordered([term(e.term, FlagKind.stop_word, rules.firm, e.term, f"\"{e.term}\" is on the firm stop-word list")
                   for e in rules.firm.entries])
    for rl in rules.ics2_lists:
        out += ordered([term(e.term, FlagKind.vague, rl, e.term.lower(),
                             f"\"{e.term}\" is listed by ICS2 as an unacceptable goods description") for e in rl.entries])
    out += ordered([term(a.alias, FlagKind.vague, rl, a.term.lower(),
                         f"\"{a.alias}\" means \"{a.term}\", which ICS2 lists as an unacceptable goods description")
                    for a in rules.aliases if (rl := rules.ics2_list_for(a.term)) is not None])
    return [t for t in out if t.words or _CJK.search(t.text)]   # a term of punctuation alone can name no goods


def check_rules(text_zh: str, text_en: str, rules: RuleSet) -> RuleMatch | None:
    """Deterministic rule match on the goods name (feature 007), the Chinese and the English one together: flagged
    only when it is nothing but listed terms and filler words, or when there is none and a listed term appears in the
    description. The flag cites the first term found, the firm list first (Stop-word), then the ICS2 lists and the
    bilingual aliases (Vague). Returns None when no rule matches (judgement follows in the tool)."""
    name_zh, name_en = goods_name(text_zh), goods_name(text_en)
    named = bool(name_zh or name_en)
    scope = f"{name_zh} {name_en}" if named else f"{text_zh or ''} {text_en or ''}"
    words, cjk = _words(scope), scope
    covered = [False] * len(words)
    first: _Term | None = None
    for t in rules.terms:
        if t.words:
            n = len(t.words)
            starts = [i for i in range(len(words) - n + 1) if tuple(words[i:i + n]) == t.words]
            for i in starts:
                covered[i:i + n] = [True] * n
            found = bool(starts)
        else:
            found = t.text in cjk
            cjk = cjk.replace(t.text, " ")
        if found and first is None:
            first = t
    if first is None:
        return None
    if named:
        rest = [w for w, c in zip(words, covered) if not c and w[0].isalpha() and len(w) > 1 and w not in FILLER]
        for filler in CJK_FILLER:
            cjk = cjk.replace(filler, " ")
        if rest or _CJK.search(cjk):
            return None
    rl = first.rule_list
    return RuleMatch(kind=first.kind, rule_source=_source_for(rl.list), matched_term=first.matched_term, list_name=rl.list,
                     source_doc=rl.source_doc, source_date=rl.source_date, reason=first.reason)


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


# --------------------------------------------------------------------------- ICS2 PDF extraction (used by the loader)
_DATE_OR_INITIAL = re.compile(r"^(\d{2}\.\d{2}\.\d{4}|Initial list)$")


def _clean_cell(cell: str | None) -> str:
    return re.sub(r"\s+", " ", cell or "").strip()


def _split_terms(raw: str) -> list[str]:
    base = re.sub(r"\(.*?\)", "", raw)
    parts = [p.strip(" .;:").lower() for p in re.split(r",|/| or ", base)]
    return [p for p in parts if len(p) >= 2]


def extract_ics2_guidance(pdf_path: Path | str, out_path: Path | str) -> int:
    """Annex table of the DG TAXUD guidance v4.10: column 0 = unacceptable term, next non-empty = acceptable example."""
    import pdfplumber

    rows: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = [_clean_cell(c) for c in row]
                    if not any(cells) or ("Unacceptable" in cells and "Acceptable" in cells):
                        continue
                    term, acceptable = cells[0], next((c for c in cells[1:] if c), "")
                    if not term:
                        continue
                    if rows and (term[0].islower() or not term[0].isalpha()):
                        rows[-1]["term"] += " " + term
                        continue
                    rows.append({"term": term, "acceptable_example": acceptable})
    seen: set[str] = set()
    entries = []
    for r in rows:
        for t in _split_terms(r["term"]):
            if t not in seen:
                seen.add(t)
                entries.append({"term": t, "lang": "en", "acceptable_example": r["acceptable_example"], "as_printed": r["term"]})
    payload = {"list": "ics2_unacceptable",
               "source_doc": "DG TAXUD Guidance on acceptable and unacceptable terms for the description of goods, v4.10 (TAXUD b.1(2021)1688480)",
               "source_date": "2021-03-04", "entries": entries}
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(entries)


def extract_ics2_stop_words(pdf_path: Path | str, out_path: Path | str, only_category: str = "goods") -> int:
    """CIRCABC 'Stop Words/Phrases in the Common Repository': the term sits left of a date or 'Initial list'."""
    import pdfplumber

    entries: list[dict] = []
    seen: set[str] = set()
    category = source = ""
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = [_clean_cell(c) for c in row]
                    joined = " ".join(cells)
                    if not any(cells) or "Stop word" in joined or "implementation date" in joined or cells[0] == "Category":
                        continue
                    date_idx = next((i for i in range(len(cells) - 1, -1, -1) if _DATE_OR_INITIAL.match(cells[i])), None)
                    if date_idx is None:
                        continue
                    term_idx = next((i for i in range(date_idx - 1, -1, -1) if cells[i]), None)
                    if term_idx is None:
                        continue
                    if cells[0] and term_idx > 0:
                        category = cells[0]
                    if term_idx > 1 and cells[1]:
                        source = cells[1]
                    raw_date = cells[date_idx]
                    if re.match(r"^\d{2}\.\d{2}\.\d{4}$", raw_date):
                        d, m, y = raw_date.split(".")
                        raw_date = f"{y}-{m}-{d}"
                    if only_category and not category.lower().startswith(only_category):
                        continue
                    for t in _split_terms(cells[term_idx]):
                        if t not in seen:
                            seen.add(t)
                            entries.append({"term": t, "lang": "en", "category": category, "implementation_date": raw_date,
                                            "origin": source, "as_printed": cells[term_idx]})
    payload = {"list": "ics2_stop_words",
               "source_doc": "Introduction of Stop Words/Phrases in the Common Repository (ICS2, CIRCABC), version in force 2026-08-03",
               "source_date": "2026-08-03", "entries": entries}
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(entries)
