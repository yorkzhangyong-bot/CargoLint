"""SC-001 acceptance aid (feature 002, task T036): what `lookup_taric` returns for the 20 acceptance codes, to compare
by hand with EZT-online on the snapshot date.

    python tests/eval/taric_acceptance.py                                            # full detail per code
    python tests/eval/taric_acceptance.py --markdown tests/eval/taric_acceptance.md  # (re)write the fill-in table

Measures the lookup leaves out by design (measures for EU country groups that contain China, research R-13) are read
straight from data/taric.jsonl and listed separately, so the comparison can mark them as the known gap.
Rewriting the Markdown file overwrites any findings already filled in.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from rag.taric import TaricMeasure, TaricStore, TaricSubdivision  # noqa: E402

SNAPSHOT = ROOT / "data" / "taric.jsonl"
AD_TYPES = {"551", "552", "553", "554", "555"}
# EU country groups that contain China on 2026-10-01 (GeographicalArea memberships, research R-13)
CHINA_GROUPS = {
    "1005": "statistical surveillance", "1008": "all third countries", "1030": "GSP eligible countries",
    "2500": "WTO members", "3100": "export restriction, protective equipment", "3200": "export restrictions, SARS-CoV",
    "3300": "export restrictions, SARS-CoV", "4002": "phytosanitary G014", "4003": "phytosanitary G016",
    "4011": "phytosanitary, Asia", "4013": "phytosanitary CN, KR, KP, RU, TW, VN", "5001": "safeguard measures",
    "5005": "safeguard measures", "5007": "safeguard, ferro-alloying elements", "5009": "safeguard, GOES",
}
# (CN-8, what the row covers): 12 subdivided, 6 with anti-dumping for China, 8 unsubdivided, 7 with group measures
# for China; every labelled subheading has at least one row.
CODES = [
    ("39249000", "subdivided · anti-dumping CN"), ("39269050", "unsubdivided"),
    ("39269097", "subdivided · group gap"), ("42022100", "subdivided"), ("61091000", "subdivided"),
    ("62034231", "unsubdivided"), ("64041100", "unsubdivided"), ("73181520", "unsubdivided · group gap"),
    ("73181542", "subdivided · anti-dumping CN · group gap"), ("73181558", "subdivided · anti-dumping CN · group gap"),
    ("73181568", "subdivided · anti-dumping CN · group gap"), ("73181582", "subdivided · anti-dumping CN · group gap"),
    ("73181595", "subdivided · anti-dumping CN · group gap"), ("84529000", "unsubdivided"), ("85183000", "subdivided"),
    ("94052140", "unsubdivided"), ("94052190", "subdivided"), ("95030075", "unsubdivided"),
    ("95030095", "subdivided"), ("96170000", "unsubdivided"),
]


def spaced(code: str) -> str:
    return " ".join([code[:4], code[4:6], code[6:8]] + ([code[8:]] if len(code) > 8 else []))


def load_raw() -> tuple[dict[str, str | None], dict[str, list[dict]]]:
    parent: dict[str, str | None] = {}
    measures: dict[str, list[dict]] = defaultdict(list)
    with SNAPSHOT.open(encoding="utf-8") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            if r["kind"] == "goods_nomenclature":
                parent[r["code"]] = r["parent"]
            else:
                measures[r["code"]].append(r)
    return parent, measures


def group_gap(code: str, parent: dict[str, str | None], measures: dict[str, list[dict]]) -> list[str]:
    """Import measures for EU groups that contain China, recorded on the code or above it: not returned by the lookup."""
    found, c = set(), code
    while c:
        found |= {f"{m['measure_type']} {m['measure_type_label']} · {m['geo_area']}" for m in measures.get(c, ())
                  if m["geo_area"] in CHINA_GROUPS and m["trade_movement"] in ("import", "both")}
        c = parent.get(c)
    return sorted(found)


def short(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def measure_line(m: TaricMeasure) -> str:
    code = f" · {m.additional_code}" if m.additional_code else ""
    return f"{m.measure_type} {m.measure_type_label} · {m.geo_area}{code} · {m.duty or 'no duty'}"


def by_scope(subs: list[TaricSubdivision], items: list[set[str]]) -> list[tuple[str, list[str]]]:
    """Items shared by every subdivision once ("all"), then each subdivision's own ("…10"); one subdivision: no label."""
    if len(subs) == 1:
        return [("", sorted(items[0]))]
    common = set.intersection(*items)
    scopes = [("all", sorted(common))] if common else []
    return scopes + [(f"…{s.code[8:]}", sorted(own - common)) for s, own in zip(subs, items) if own - common]


def measure_cell(subs: list[TaricSubdivision], gaps: list[set[str]]) -> str:
    def lines(s: TaricSubdivision) -> set[str]:
        plain = {measure_line(m) for m in s.measures if m.measure_type not in AD_TYPES}
        ad = defaultdict(int)
        for m in s.measures:
            if m.measure_type in AD_TYPES:
                ad[f"{m.measure_type} {m.measure_type_label} · {m.geo_area} · regulation {m.regulation_id}"] += 1
        return plain | {f"{k}: {n} additional code{'' if n == 1 else 's'} (appendix)" for k, n in ad.items()}
    out = []
    for scope, items in by_scope(subs, [lines(s) for s in subs]):
        out += ([f"*{scope}*"] if scope else []) + [f"· {i}" for i in items]
    gap = by_scope(subs, gaps) if any(gaps) else []
    if gap:
        out.append("**not returned, group gap:**")
        out += [f"· {i}" + (f" ({scope})" if scope not in ("", "all") else "") for scope, items in gap for i in items]
    return "<br>".join(out).replace("|", "/")


# --------------------------------------------------------------------------- EZT-online check
EZT = Path(__file__).with_name("taric_acceptance_ezt.json")
UNIT_CODES = {"100 kg": "DTN", "kg": "KGM", "1000 kg": "TNE", "l": "LTR", "hl": "HLT", "m³": "MTQ", "m²": "MTK", "p/st": "NAR"}
COND = "conditions"


def norm_ours(duty: str) -> str:
    if not duty:
        return ""
    if " with " in duty or "otherwise" in duty or " if " in duty:
        return COND
    if duty in UNIT_CODES:
        return UNIT_CODES[duty]
    if re.fullmatch(r"[A-Z]{3}( [A-Z])?", duty):
        return duty.split()[0]
    return duty.replace(" ", "")


def norm_ezt(duty: str) -> str:
    """EZT-online writes "3,7%", "3 EURO", "NPR = Anzahl Paar", "-" for no duty, and appends the company (or "Andere",
    other companies) to anti-dumping rates, as in "86,5%Andere"."""
    if duty.startswith("Weitere Informationen siehe Bedingungen"):
        return COND
    if duty == "-":
        return ""
    unit = re.match(r"^([A-Z]{3}) = ", duty)
    if unit:
        return unit.group(1)
    duty = re.sub(r"(%)\s*[A-Za-zÄÖÜäöüß].*$", r"\1", duty)
    return duty.replace(",", ".").replace("EURO", "EUR").replace(" ", "")


def compare(ours: tuple[TaricMeasure, ...], rows: list[dict], geo: str) -> dict:
    """Our measures for one area against EZT-online's rows, keyed by (measure type, additional code)."""
    mine = {(m.measure_type, m.additional_code or ""): norm_ours(m.duty) for m in ours if m.geo_area == geo}
    theirs = {(r["mn"], "" if r["zc"] == "-" else r["zc"]): norm_ezt(r["duty"]) for r in rows if r["geo"] == geo}
    same = {k for k in mine if k in theirs and (mine[k] == theirs[k] or (mine[k] == "" and theirs[k] == COND))}
    return {"ezt": len(theirs), "matched": len(same), "only_ours": sorted(set(mine) - set(theirs)),
            "only_ezt": sorted(set(theirs) - set(mine)),
            "differs": sorted((k, mine[k], theirs[k]) for k in mine if k in theirs and k not in same)}


def area_cell(results: list[dict]) -> str:
    ezt, matched = sum(r["ezt"] for r in results), sum(r["matched"] for r in results)
    out = [f"{matched} of {ezt} rows match" if ezt else "no rows"]
    for label, key in (("only in EZT-online", "only_ezt"), ("only in CargoLint", "only_ours")):
        items = sorted({" ".join(x for x in k if x) for r in results for k in r[key]})
        if items:
            out.append(f"{label}: " + ", ".join(items))
    diffs = sorted({f"{' '.join(x for x in k if x)} ours {a or 'no duty'} / EZT {b}" for r in results for k, a, b in r["differs"]})
    if diffs:
        out.append("duty differs: " + "; ".join(diffs))
    return "<br>".join(out)


def ezt_check(store: TaricStore, ezt: dict) -> tuple[list[str], dict[tuple[str, str], str]]:
    rows, companies = [], {}
    for i, (cn8, _) in enumerate(CODES, 1):
        subs = store.lookup_taric(cn8)
        entry = ezt["codes"][cn8]
        theirs10 = sorted({e["code"][:10] for e in entry["tree"]["end_lines"]})
        ours10 = [s.code for s in subs]
        if theirs10 == ours10:
            sub_cell = f"match: {len(ours10)} of {len(ours10)}"
        else:
            sub_cell = "<br>".join(x for x in (
                "only in EZT-online: " + ", ".join(sorted(set(theirs10) - set(ours10))) if set(theirs10) - set(ours10) else "",
                "only in CargoLint: " + ", ".join(sorted(set(ours10) - set(theirs10))) if set(ours10) - set(theirs10) else "") if x)
        per = {s.code: entry["measures"].get(s.code, {"rows": []})["rows"] for s in subs}
        cn = [compare(s.measures, per[s.code], "CN") for s in subs]
        eo = [compare(s.measures, per[s.code], "1011") for s in subs]
        g1008 = sorted({f"{r['mn']} {r['type']}" for rs in per.values() for r in rs if r["geo"] == "1008"})
        for rs in per.values():
            for r in rs:
                if r["geo"] == "CN" and r["zc"] != "-":
                    company = re.sub(r"^[\d.,]+\s*%\s*", "", r["duty"].replace("Weitere Informationen siehe Bedingungen", "").strip())
                    companies[(r["mn"], r["zc"])] = "Andere (other companies)" if company == "Andere" else company
        clean = theirs10 == ours10 and not any(r["only_ours"] or r["only_ezt"] or r["differs"] for r in cn + eo)
        rows.append(f"| {i} | {spaced(cn8)} | {sub_cell} | {area_cell(cn)} | {area_cell(eo)} | "
                    f"{'<br>'.join(g1008) + '<br>(not in CargoLint: known gap)' if g1008 else 'none'} | "
                    f"{'match' + (' apart from the 1008 gap' if g1008 else '') if clean else 'differences, see row'} |")
    return rows, companies


def sample_rows(samples: list[dict]) -> list[str]:
    """EZT-online's Bedingungen for sample anti-dumping codes, rewritten in CargoLint's wording and compared."""
    out = []
    for s in samples:
        rows = [r for r in s["ezt"]["rows"] if len(r) == 5]
        clauses, fallbacks, shown = [], [], []
        for seq, _, _, amount, doc in rows:
            code = re.search(r"Schlüssel: (\w+)\)", doc)
            value = f"{amount.replace(',', '.')} %"
            (clauses if code else fallbacks).append(
                f"{value} with anti-dumping/countervailing document {code.group(1)}" if code else f"otherwise {value}")
            shown.append(f"{seq}: {amount} {'with ' + code.group(1) if code else 'without a document'}")
        ezt_text = "; ".join(clauses + fallbacks) if rows else norm_ezt(s["ezt"]["duty_cell"]).replace("%", " %")
        if not rows:
            shown = [s["ezt"]["duty_cell"]]
        result = "match" if ezt_text == s["cargolint"] else "differs"
        out.append(f"| {s['code']} | {s['zc']} | {' · '.join(shown)} | {s['cargolint']} | {result} |")
    return out


def details(store: TaricStore, parent, measures) -> None:
    for cn8, covers in CODES:
        subs = store.lookup_taric(cn8)
        print(f"\n=== {spaced(cn8)} · {covers}")
        for s in subs:
            print(f"  {s.code}  {s.description or '(the CN-8 line itself)'}")
            for m in s.measures:
                print(f"      {measure_line(m)}  [on {m.recorded_on}; {m.regulation_ref or m.regulation_id}]")
            for g in group_gap(s.code, parent, measures):
                print(f"      not returned (group gap): {g} ({CHINA_GROUPS[g.rsplit(' · ', 1)[1]]})")


def markdown(store: TaricStore, parent, measures) -> str:
    head = store.snapshot
    rows = []
    appendix: dict[tuple[str, str, str, str], dict[str | None, set[str]]] = defaultdict(lambda: defaultdict(set))
    for i, (cn8, covers) in enumerate(CODES, 1):
        subs = store.lookup_taric(cn8)
        gaps = [set(group_gap(s.code, parent, measures)) for s in subs]
        for s in subs:
            for m in s.measures:
                if m.measure_type in AD_TYPES:
                    appendix[(m.regulation_id, m.regulation_ref, m.measure_type, m.measure_type_label)][m.additional_code].add(m.duty)
        enter = f"A: `{cn8}`<br>B: " + ", ".join(f"`{s.code}`" for s in subs)
        subdivisions = "<br>".join(f"{s.code} {short(s.description) or '(the CN-8 line itself)'}" for s in subs).replace("|", "/")
        rows.append(f"| {i} | {spaced(cn8)} | {covers} | {enter} | {subdivisions} | {measure_cell(subs, gaps)} |  |")
    out = [
        "# SC-001 acceptance: TARIC lookup against EZT-online",
        "",
        f"Snapshot {head.snapshot_date}, batch `{head.batch_id}`. Generated by `python tests/eval/taric_acceptance.py --markdown "
        "tests/eval/taric_acceptance.md`; regenerating overwrites the findings. CargoLint shows only what "
        "`lookup_taric(cn8, origin=\"CN\")` returns: import measures for China (CN) and erga omnes (1011), recorded on the "
        "subdivision or any level above it. Duty texts are display text; conditions are shown, never evaluated.",
        "",
        "## EZT-online steps (the site works in sessions, so there are no stable per-code links)",
        "",
        "Every query, A and B alike, uses **maßgeb. Zeitpunkt** `01.10.2026` and **Ursprungsland** `CN`, so the results "
        "match the snapshot date and the China filter; set both on **Suchkriterien** before each search.",
        "",
        "1. Open https://auskunft.ezt-online.de/ezto/Welcome.do, set **maßgeb. Zeitpunkt** to `01.10.2026`, click "
        "**ändern**, then **zur Einfuhr**.",
        "2. **A, subdivisions**: on **Suchkriterien** enter the CN-8 in **Codenummer** and `CN` in **Ursprungsland**, tick **automatischer Wechsel in "
        "die Warennomenklatur** and click **Suche starten**. In the **Ordner** view, open the CN-8 line and any sub-folders "
        "until only end lines remain. EZT-online shows 11 digits; the 11th is the German national digit, so compare the "
        "first 10.",
        "3. **B, measures**: back on **Suchkriterien**, untick the box, enter one 10-digit code from the row in "
        "**Codenummer** and `CN` in **Ursprungsland**, and click **Suche starten**. On **Maßnahmen und Hinweise**, the "
        "**Einfuhrmaßnahmen** table may span several pages:",
        "   - compare the rows whose **Gebietscode** is `CN`, and mark the `1011` (erga omnes) rows separately; **MN-Schl.** "
        "is the measure type and **ZC** the additional code;",
        "   - where the duty reads \"Weitere Informationen siehe Bedingungen\", open **Bedingungen** (company-specific "
        "anti-dumping rates with document D008);",
        "   - mark the `1008` (all third countries) rows separately too. They and the other groups that contain China (`1005`, `1030`, `2500`, `4002`, `4003`, `4011`, `4013`, "
        "`5001`, `5005`, `5007`, `5009`, `3100`, `3200`, `3300`) are the known gap: expected in EZT-online, missing in "
        "CargoLint;",
        "   - rows for other countries and groups, such as preferences 142 or 106 for TR, AD and SM, are outside the "
        "lookup.",
        "",
        "In **Finding**, write `match`, `mismatch: <what differs>` or `gap: <the expected known-limitation row>`.",
        "",
        "| # | CN-8 | Covers | EZT-online: enter | CargoLint subdivisions | CargoLint measures for China (type · area · duty) | Finding |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## Appendix: anti-dumping and countervailing measures for China, by regulation",
        "",
        "Every additional code with its duty text. In EZT-online the code is the **ZC** column; conditional rates are under "
        "**Bedingungen**.",
    ]
    companies: dict[tuple[str, str], str] = {}
    if EZT.exists():
        ezt = json.loads(EZT.read_text(encoding="utf-8"))
        check, companies = ezt_check(store, ezt)
        out[out.index("## Appendix: anti-dumping and countervailing measures for China, by regulation"):0] = [
            f"## EZT-online check, run automatically on {ezt['fetched'][:10]}",
            "",
            f"Each query used maßgeb. Zeitpunkt {ezt['date']} and Ursprungsland {ezt['origin']}. Subdivisions compare the first "
            "10 digits of EZT-online's 11-digit end lines. Measures compare type, additional code and duty; a duty shown as "
            "\"Weitere Informationen siehe Bedingungen\" counts as a match for a CargoLint conditional duty or a control without a "
            "duty, but its rates are not compared. The `1011` (erga omnes) and `1008` (all third countries) rows are kept "
            "apart from the `CN` rows. Raw rows: `tests/eval/taric_acceptance_ezt.json`.",
            "",
            "| # | CN-8 | Subdivisions (first 10 digits) | CN rows | 1011 rows (erga omnes) | 1008 rows (all third countries) | Result |",
            "|---|---|---|---|---|---|---|",
            *check,
            "",
            "Sample conditions, read from EZT-online's **Bedingungen** page and rewritten in CargoLint's wording:",
            "",
            "| Code | Additional code | EZT-online conditions | CargoLint duty text | Result |",
            "|---|---|---|---|---|",
            *sample_rows(ezt.get("condition_samples", [])),
            "",
        ]
    for (reg, ref, mtype, label), codes in sorted(appendix.items()):
        out += ["", f"### {mtype} {label}, regulation {reg} ({ref or 'no OJ reference'}): {len(codes)} additional code{'' if len(codes) == 1 else 's'}", "",
                "| Additional code | Duty text | EZT-online (company) | Finding |", "|---|---|---|---|"]
        out += [f"| {code or '(none)'} | {' / '.join(sorted(d or 'no duty' for d in duties))} | "
                f"{('present' + (': ' + companies[(mtype, code)] if companies[(mtype, code)] else '')) if (mtype, code) in companies else ('not seen' if companies else '')} |  |"
                for code, duties in sorted(codes.items(), key=lambda t: t[0] or "")]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="SC-001 acceptance aid: lookup_taric results for the 20 acceptance codes")
    ap.add_argument("--markdown", type=Path, help="write the fill-in table to this file")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    store = TaricStore.from_jsonl(SNAPSHOT)
    parent, measures = load_raw()
    if args.markdown:
        args.markdown.write_text(markdown(store, parent, measures), encoding="utf-8", newline="\n")
        print(f"wrote {args.markdown}")
    else:
        details(store, parent, measures)
    return 0


if __name__ == "__main__":
    sys.exit(main())
