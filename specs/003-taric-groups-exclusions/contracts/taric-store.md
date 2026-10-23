# Contract: TaricStore and `lookup_taric`, changes for groups and exclusions

Changes feature 002's [taric-store.md](../../002-taric-snapshot-load/contracts/taric-store.md). Everything not named
here is unchanged: `TaricFileError`, `TaricSnapshotInfo`, `TaricSubdivision`, the input rules of `lookup_taric`, the
knowledge-base wiring (`kb.taric`, loaded once at app start) and the TARIC caption. Field meanings:
[data-model.md](../data-model.md) §6.

## Store

```python
# rag/taric.py
@dataclass(frozen=True, slots=True)
class TaricMeasure:
    sid: int
    recorded_on: str              # the code the measure is recorded against (the subdivision or an ancestor)
    measure_type: str
    measure_type_label: str
    geo_area: str                 # the measure's own area: the origin, a group containing it, or 1011
    geo_area_name: str            # NEW: English name of geo_area valid on the snapshot date; "" when none (FR-008)
    additional_code: str | None
    duty: str
    regulation_id: str
    regulation_ref: str
    valid_from: date
    valid_to: date | None

class TaricStore:
    @classmethod
    def from_jsonl(cls, path: Path | str) -> "TaricStore": ...   # schema 2 only; FileNotFoundError / TaricFileError as before
    @property
    def snapshot(self) -> TaricSnapshotInfo: ...                  # unchanged
    def lookup_taric(self, cn8: str, origin: str = "CN") -> list[TaricSubdivision]: ...   # signature unchanged
```

## `lookup_taric(cn8, origin="CN")`

Inputs, subdivisions, the empty result and the order of measures are as in feature 002. Each subdivision's `measures`
are now those recorded against the subdivision or any code in its parent chain for which all of these hold:

| Rule | Source |
|---|---|
| `geo_area` is in the origin's applicable area set: the origin, every group reached from it through the snapshot's memberships (any depth), and `1011` | FR-005, FR-006 |
| none of the measure's excluded areas is in that set | FR-006 |
| the trade movement is `import` or `both` | FR-007 (as feature 002) |
| the measure type is not `566` | FR-007 |

Each returned measure keeps its own `geo_area` and carries `geo_area_name` (FR-008). An origin with no memberships gets
its own measures and the erga omnes ones, less those that exclude it. Group measures are recorded once per measure, so a
group reached by two paths, or `1011` appearing as a group, never duplicates a measure.

Guarantees:
- Read-only; results are frozen; equal calls return equal results (feature 002, FR-020).
- Everything returned is valid on the snapshot date.
- A lookup answers in well under 1 second.
- The snapshot is read once at app start. With the snapshot present, the knowledge base opens at most 2 s later than
  without it (FR-011, SC-004), measured with `tests/eval/kb_load_time.py` as in T037. Export-only and type-566 measures
  are not held in memory (research R-07).

## Knowledge-base wiring and caption

Unchanged. A schema-1 file is refused like any other schema: `kb.taric = None`, the reason is logged, and the caption
reads `TARIC not loaded` until the next `--taric` run and a restart.
