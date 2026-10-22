# Contract: TaricStore, knowledge-base wiring and the TARIC caption

Consumers: Spec 2 (agent, Candidate schema, UI) and the sidebar. Field meanings: [data-model.md](../data-model.md) §6.

## Store

```python
# rag/taric.py
class TaricFileError(Exception): ...            # malformed line, missing snapshot record, unsupported schema

@dataclass(frozen=True, slots=True)
class TaricSnapshotInfo:
    snapshot_date: date
    batch_id: str
    loaded_at: str
    goods_records: int
    measure_records: int
    cn8_mismatches: int

@dataclass(frozen=True, slots=True)
class TaricMeasure:
    sid: int
    recorded_on: str                            # the code the measure is recorded against (the subdivision or an ancestor)
    measure_type: str
    measure_type_label: str
    geo_area: str
    additional_code: str | None
    duty: str
    regulation_id: str
    regulation_ref: str
    valid_from: date
    valid_to: date | None

@dataclass(frozen=True, slots=True)
class TaricSubdivision:
    code: str
    description: str
    valid_from: date
    valid_to: date | None
    measures: tuple[TaricMeasure, ...]

class TaricStore:
    @classmethod
    def from_jsonl(cls, path: Path | str) -> "TaricStore": ...   # FileNotFoundError when absent; TaricFileError when unreadable
    @property
    def snapshot(self) -> TaricSnapshotInfo: ...
    def lookup_taric(self, cn8: str, origin: str = "CN") -> list[TaricSubdivision]: ...
```

## `lookup_taric(cn8, origin="CN")`

| Input | Rule |
|---|---|
| `cn8` | spaces and dots removed; must then be exactly 8 digits, else `ValueError` (FR-019) |
| `origin` | a geographical area id such as `CN`; upper-cased; empty or non-alphanumeric → `ValueError` |

Result:
- The declarable codes whose `cn8` equals the input, in code order (FR-017). For a CN-8 that TARIC does not subdivide this is the single code ending in 00; for a subdivided CN-8 it is the codes beneath it, never the CN-8's own 00 code.
- `[]` when TARIC has no declarable code for that CN-8 on the snapshot date (FR-019).
- Each subdivision's `measures`: those recorded against the subdivision or any code in its parent chain (CN-8, subheading, heading, chapter, and intermediate TARIC levels), whose `geo_area` is the origin or `1011`, and whose trade movement is `import` or `both` (FR-018; research R-07). Ordered by (`measure_type`, `geo_area`, `additional_code` or "", `sid`).
- Each measure carries its additional code when it has one (clarification Q1). Measures for country groups that contain the origin, erga omnes measures that exclude it, and additional-code descriptions are not covered (spec known limitation; sized in research R-13).

Guarantees:
- Read-only: no method changes the store; results are frozen; equal calls return equal results (FR-020).
- Everything returned is valid on the snapshot date.
- A lookup answers in well under 1 second (SC-007): dictionary access by CN-8 and by code.

## Knowledge-base wiring

```python
# rag/loader.py
class KnowledgeBase:
    taric: TaricStore | None                     # None when data/taric.jsonl is absent, unreadable or of another schema

def open_knowledge_base(settings=None, usage_sink=None) -> KnowledgeBase: ...
    # loads data/taric.jsonl once (app start, cached by st.cache_resource);
    # on FileNotFoundError / TaricFileError: kb.taric = None, reason logged; the app starts normally (FR-024)
```

```python
# rag/nomenclature.py
class NomenclatureIndex:
    def cn8_codes(self) -> frozenset[str]: ...   # the 8-digit codes of the "CN dddd dd dd" lines in all chunk texts
```

## TARIC caption

```python
# ui/sidebar.py
def taric_caption(kb) -> str: ...
```

| State | Text |
|---|---|
| snapshot loaded | `TARIC snapshot 2026-10-01 · 105 CN-8 mismatches` (`1 CN-8 mismatch` when the count is 1) |
| absent, unreadable or other schema | `TARIC not loaded` |

Rendered with `st.caption` inside the existing "Knowledge base" sidebar expander, directly under the existing knowledge-base caption. No other screen element changes (FR-024).
