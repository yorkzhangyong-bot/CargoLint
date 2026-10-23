"""SC-004 (feature 004, task T048): for the 20 acceptance codes of feature 002 and origin CN, the subdivisions and
measures the detail card shows (`taric_view`, through the agent's `line_taric_view`) equal `lookup_taric`'s output, and
each measure sits in exactly one group.

    python tests/eval/taric_ui_parity.py

Reads the real snapshot data/taric.jsonl and needs no key. Prints "N of 20" with each difference and exits non-zero on
any difference.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import TARIC_SNAPSHOT  # noqa: E402
from agent.taric_rules import GROUPS, measure_group, taric_view  # noqa: E402
from rag.taric import TaricStore  # noqa: E402
from tests.eval.taric_acceptance import CODES  # noqa: E402

ORIGIN = "CN"


def differences(store: TaricStore, cn8: str, origin: str = ORIGIN) -> tuple[list[str], dict[str, int]]:
    """What the view shows against what the lookup returned; [] when they are equal. Also the group sizes."""
    subs = store.lookup_taric(cn8, origin)
    view = taric_view(subs, origin, store.snapshot.snapshot_date, None)
    out: list[str] = []
    if [sv.code for sv in view.subdivisions] != [s.code for s in subs]:
        out.append("the subdivisions differ")
    sizes = Counter()
    for sv, s in zip(view.subdivisions, subs):
        if sv.description != s.description:
            out.append(f"{s.code}: the description differs")
        shown = [m for g in GROUPS for m in sv.groups[g]]
        if Counter(shown) != Counter(s.measures):          # same measures, field by field: none added, dropped or altered
            out.append(f"{s.code}: {len(shown)} measures shown, {len(s.measures)} returned, or a field differs")
        for g in GROUPS:                                   # each in exactly one group, in the returned order
            expected = [m for m in s.measures if measure_group(m.measure_type) == g]
            if list(sv.groups[g]) != expected:
                out.append(f"{s.code}: the {g} group differs from the lookup")
            sizes[g] += len(sv.groups[g])
    return out, dict(sizes)


def main() -> int:
    store = TaricStore.from_jsonl(TARIC_SNAPSHOT)
    print(f"TARIC snapshot {store.snapshot.snapshot_date}, origin {ORIGIN}: taric_view against lookup_taric")
    equal = 0
    for cn8, note in CODES:
        diffs, sizes = differences(store, cn8)
        subs = len(store.lookup_taric(cn8, ORIGIN))
        status = "equal" if not diffs else "DIFFERENT"
        equal += not diffs
        print(f"  {cn8}  {status:9}  {subs:2} subdivision{'s' if subs != 1 else ' '}; measures shown: "
              + ", ".join(f"{g.replace('_', ' ')} {sizes.get(g, 0)}" for g in GROUPS) + f"  ({note})")
        for d in diffs:
            print(f"      - {d}")
    print(f"SC-004: {equal} of {len(CODES)} codes show exactly what lookup_taric returns")
    return 0 if equal == len(CODES) else 1


if __name__ == "__main__":
    sys.exit(main())
