# Contract: TARIC load command, changes for groups and exclusions

Changes feature 002's [loader-cli.md](../../002-taric-snapshot-load/contracts/loader-cli.md). Synopsis, preconditions,
options, exit codes, guarantees and the data-source register row are unchanged; the command still reads only the six
object files, needs no network and no secret, and never touches a search index (FR-013).

## Steps (changed)

4. **Skip check**: as before, the run stops with the skip message when `data/taric.jsonl` holds a readable schema-2
   snapshot of the same date and `--force` is absent. A file of another schema, or one that cannot be read, never causes a
   skip: the run logs why it will rewrite the file and continues (FR-003).
7. **Parsing**: as before, plus:
   - from GeographicalArea, the EU areas valid on D with their English names valid on D and their memberships valid on
     D (research R-01, R-02);
   - from Measure, each kept measure's EU excluded areas (research R-03);
   - a membership naming a group SID that is not an EU area stops the run (exit 1, the member and SID named).

All other steps are unchanged.

## Output (changed)

Progress lines, from the loader's log:

```text
[loader] taric: data/taric.jsonl will be rewritten: schema 1 is not supported (expected 2)
[loader] taric: parsed in <seconds> s; 314 EU geographical areas
```

The first line appears only when an existing file is of another schema or unreadable; the text after the colon is the
reader's reason. The second line now counts the EU areas valid on D that the snapshot stores.

Summary on success (values from the 2026-10-01 extract), with one new line (FR-004):

```text
TARIC snapshot 2026-10-01 · batch <batch> · export 3dc153a8-7542-4d91-8157-b7784f72797b
6 files verified with key 410160CE25CEC2FF322784E7302AC3C1D0E3E1C9: GoodsNomenclature_<batch>_261001.xml.gz.pgp, …
code records 22,361 (16,742 declarable) · measure records 161,959
area names 314 · group memberships 2,805 · measures with excluded areas 10,581
CN-8 mismatches 105 → store/logs/taric-cn8-mismatches-2026-10-01.txt
replaced snapshot (older format or unreadable)
wrote data/taric.jsonl (<size> MB) in <seconds> s
```

The new line counts the areas stored with a non-empty name, the `member_of` entries over all areas, and the measures
with at least one excluded area. "replaced snapshot …" reads `new snapshot` or `replaced snapshot <date>` as before when
the previous file was absent or a readable schema-2 snapshot.

## Internal interfaces (changed)

```python
# rag/taric_extract.py
def parse_geographical_areas(payload: bytes, d: date) -> list[TaricAreaRecord]: ...   # EU areas valid on D, by id
@dataclass
class Snapshot:
    ...                                    # header, codes, measures, mismatches, log_path, dropped as before
    areas: list[TaricAreaRecord]           # replaces geo_areas: frozenset[str]

# rag/taric.py
@dataclass(frozen=True, slots=True)
class TaricAreaRecord:                     # NEW record kind "geographical_area"
    geo_area: str
    name: str
    member_of: tuple[str, ...]
# TaricMeasureRecord gains: excluded_areas: tuple[str, ...]
# record_to_line / line_to_record: snapshot record as an object, every other kind as a positional array
```
