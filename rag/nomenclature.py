"""CN 2026 SKOS RDF/XML → one chunk per HS-6 subheading, and the nomenclature index used by
`validate_code` (research.md R-11, constitution Principle IV)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from lxml import etree

from agent.schemas import NomenclatureChunk

NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xkos": "http://rdf-vocabulary.ddialliance.org/xkos#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dct": "http://purl.org/dc/terms/",
    "adms": "http://www.w3.org/ns/adms#",
}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
RDF_ABOUT = "{%s}about" % NS["rdf"]
RDF_RESOURCE = "{%s}resource" % NS["rdf"]
_DASHES = re.compile(r"^[\s\-–—]+")
_LEADING_CODE = re.compile(r"^\s*(\d{2,4}(?:\s\d{2})*)\s*")


@dataclass
class Concept:
    uri: str
    notation: str = ""
    code: str = ""           # digits only ("961700"); empty for sections and text-only lines
    depth: int | None = None
    broader: str | None = None
    pref_en: str = ""
    alt_en: str = ""
    scope_note: str = ""
    dashes: str = ""
    identifier: str = ""
    narrower: list[str] = field(default_factory=list)

    @property
    def label_en(self) -> str:
        text = self.alt_en or self.pref_en
        if not self.alt_en and text:
            text = _LEADING_CODE.sub("", text, count=1)
        return _DASHES.sub("", text).strip()


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_skos(path: Path | str) -> Iterator[Concept]:
    """Stream the SKOS file; yields one Concept per skos:Concept / rdf:Description with rdf:about."""
    wanted = {"{%s}Concept" % NS["skos"], "{%s}Description" % NS["rdf"]}
    for _event, elem in etree.iterparse(str(path), events=("end",), huge_tree=True):
        if elem.tag not in wanted:
            continue
        about = elem.get(RDF_ABOUT)
        if not about:
            continue
        c = Concept(uri=about)
        for child in elem:
            name = _local(child.tag)
            lang = child.get(XML_LANG)
            text = (child.text or "").strip()
            if name == "notation":
                c.notation = text
                digits = re.sub(r"\s+", "", text)
                c.code = digits if digits.isdigit() else ""
            elif name == "depth":
                try:
                    c.depth = int(text)
                except ValueError:
                    pass
            elif name == "broader":
                c.broader = child.get(RDF_RESOURCE) or text or None
            elif name == "narrower":
                res = child.get(RDF_RESOURCE)
                if res:
                    c.narrower.append(res)
            elif name == "prefLabel" and (lang in (None, "en")):
                if lang == "en" or not c.pref_en:
                    c.pref_en = text
            elif name == "altLabel" and (lang in (None, "en")):
                if lang == "en" or not c.alt_en:
                    c.alt_en = text
            elif name == "scopeNote" and (lang in (None, "en")):
                if lang == "en" or not c.scope_note:
                    c.scope_note = text
            elif name == "hiddenLabel":
                c.dashes = text
            elif name == "identifier" and not c.identifier:
                c.identifier = text
        elem.clear()
        yield c


def _dotted(code6: str) -> str:
    return f"{code6[:4]}.{code6[4:6]}"


def _spaced(code: str) -> str:
    return " ".join([code[:4]] + [code[i:i + 2] for i in range(4, len(code), 2)])


def build_chunks(concepts: Iterable[Concept], source: str = "EU Combined Nomenclature 2026 (ESTAT-CN2026 SKOS)",
                 edition_year: int = 2026) -> list[NomenclatureChunk]:
    concepts = list(concepts)
    by_uri = {c.uri: c for c in concepts}
    children: dict[str, list[Concept]] = {}
    for c in concepts:
        if c.broader:
            children.setdefault(c.broader, []).append(c)

    def ancestor_with_len(c: Concept, n: int) -> Concept | None:
        cur = c
        seen = 0
        while cur.broader and seen < 12:
            cur = by_uri.get(cur.broader)  # type: ignore[assignment]
            if cur is None:
                return None
            if len(cur.code) == n:
                return cur
            seen += 1
        return None

    def descendants(c: Concept) -> list[Concept]:
        out: list[Concept] = []
        stack = list(children.get(c.uri, []))
        while stack:
            d = stack.pop(0)
            out.append(d)
            stack = list(children.get(d.uri, [])) + stack
        return out

    chunks: list[NomenclatureChunk] = []
    for c in concepts:
        if len(c.code) != 6:
            continue
        heading = ancestor_with_len(c, 4)
        chapter = ancestor_with_len(c, 2)
        dotted = _dotted(c.code)
        lines = []
        if chapter is not None:
            lines.append(f"Chapter {chapter.code} — {chapter.label_en}")
        if heading is not None:
            lines.append(f"Heading {heading.code} — {heading.label_en}")
        lines.append(f"Subheading {dotted} — {c.label_en}")
        if c.scope_note:
            lines.append(c.scope_note)
        for d in descendants(c):
            if d.code and len(d.code) >= 8:
                lines.append(f"CN {_spaced(d.code)} — {d.label_en}")
            elif not d.code and d.label_en:
                lines.append(f"{d.dashes} {d.label_en}".strip())
            if d.scope_note:
                lines.append(d.scope_note)
        chunks.append(NomenclatureChunk(
            id=f"hs:{dotted}", text="\n".join(lines),
            metadata={"chapter": c.code[:2], "heading": c.code[:4], "subheading": dotted, "language": "en",
                      "source": source, "edition_year": edition_year},
        ))
    chunks.sort(key=lambda ch: ch.id)
    return chunks


def write_jsonl(chunks: Iterable[NomenclatureChunk], path: Path | str) -> int:
    n = 0
    with Path(path).open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps({"id": ch.id, "text": ch.text, "metadata": ch.metadata}, ensure_ascii=False) + "\n")
            n += 1
    return n


class NomenclatureIndex:
    """Code set + subheading text lookup; the authority for `validate_code`."""

    def __init__(self, chunks: list[NomenclatureChunk]) -> None:
        self.chunks = chunks
        self._by_code: dict[str, NomenclatureChunk] = {ch.metadata.get("subheading", ch.id.split(":")[-1]): ch for ch in chunks}

    @classmethod
    def from_jsonl(cls, path: Path | str) -> "NomenclatureIndex":
        chunks = []
        with Path(path).open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(NomenclatureChunk.model_validate(json.loads(line)))
        return cls(chunks)

    def __contains__(self, code: object) -> bool:
        return isinstance(code, str) and code in self._by_code

    def __len__(self) -> int:
        return len(self._by_code)

    @property
    def codes(self) -> list[str]:
        return list(self._by_code)

    def get(self, code: str) -> NomenclatureChunk | None:
        return self._by_code.get(code)

    def subheading_text(self, code: str) -> str:
        ch = self._by_code.get(code)
        if ch is None:
            return ""
        for line in ch.text.splitlines():
            if line.startswith("Subheading "):
                return line.split("—", 1)[-1].strip()
        return ch.text.splitlines()[0]

    def chapter_of(self, code: str) -> str:
        return code[:2]

    @property
    def edition_year(self) -> int | None:
        return self.chunks[0].metadata.get("edition_year") if self.chunks else None

    @property
    def source(self) -> str:
        return self.chunks[0].metadata.get("source", "") if self.chunks else ""
