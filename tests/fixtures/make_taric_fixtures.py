"""Builds the TARIC fixture extract in tests/fixtures/taric/ (feature 002, task T003, research R-12). Needs gpg.

    python tests/fixtures/make_taric_fixtures.py

Six tiny object files in the real Arctic Group export format are written twice: as plain XML for the parser
tests (taric/xml/) and gzipped and signed like the real files for the signature and loader tests
(taric/extract/). Both throwaway key pairs are created in a temporary gpg home that is deleted at the end, so
only their public keys and the signed files are kept, never a secret key. Every run makes new keys; their
fingerprints go into taric/expected.json together with the counts the tests assert.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "taric"
NS = "http://www.arcticgroup.se/tariff/arctictariff/export"
BATCH = "11111111-2222-4333-8444-555555555555"     # equals the export id, as in the real files
OTHER_EXPORT_ID = "99999999-8888-4777-8666-555555555555"
YYMMDD = "261001"                                  # snapshot date D = 2026-10-01
REAL_SIGNED = ROOT / "data" / "raw" / "taric" / "DutyExpression_3dc153a8-7542-4d91-8157-b7784f72797b_261001.xml.gz.pgp"


def _attrs(**values: str | None) -> str:
    return " ".join(f"at:{k}={quoteattr(v)}" for k, v in values.items() if v is not None)


def export(object_name: str, items: list[str], export_id: str = BATCH) -> bytes:
    body = "".join(f"\t\t{item}\n" for item in items)
    return (f"<?xml version='1.0' encoding='UTF-8'?>\n<export xmlns=\"{NS}\" xmlns:at=\"{NS}\">\n\t<id>{export_id}</id>\n"
            f"\t<exportType>{object_name}Object</exportType>\n\t<parameters>\n\t\t<queryDateStart>2014-01-01</queryDateStart>\n"
            f"\t</parameters>\n\t<items>\n{body}\t</items>\n</export>\n").encode("utf-8")


# --------------------------------------------------------------------------- GoodsNomenclature
def goods(code: str, suffix: str, indents: list[tuple[str, int]], periods: list[tuple[str, dict[str, str]]],
          start: str = "1990-01-01", end: str | None = None, national: str = "0") -> str:
    inner = "".join(f"<goodsNomenclatureIndent {_attrs(national=national, quantityIndents=f'{n:02d}', dateStart=ds)}/>"
                    for ds, n in indents)
    for ds, texts in periods:
        descs = "".join(f"<goodsNomenclatureDescription {_attrs(description=t, languageId=lang, national=national)}/>"
                        for lang, t in texts.items())
        inner += f"<goodsNomenclatureDescriptionPeriod {_attrs(national=national, dateStart=ds)}>{descs}</goodsNomenclatureDescriptionPeriod>"
    head = _attrs(goodsNomenclatureCode=code, national=national, productLineSuffix=suffix, dateStart=start, dateEnd=end,
                  statisticalIndicator="0", changeType="U")
    return f"<goodsNomenclature {head}>{inner}</goodsNomenclature>"


def g(code: str, suffix: str, indent: int, en: str | None, **kw) -> str:
    return goods(code, suffix, [("1990-01-01", indent)], [("1990-01-01", {"EN": en, "SV": "Svensk text"} if en else {"SV": "Svensk text"})], **kw)


# Written out of order on purpose: the loader must sort. Stored suffix-80 codes (11) and their expected hierarchy:
#   7300000000 chapter, parent None            7318000000 heading, parent 7300000000
#   7318150000 HS-6, parent 7318000000 (the suffix-10 grouping line 7318110000 is skipped)
#   7318155800 CN-8 own code, parent of 7318155810 and 7318155890 (the latter under grouping line 7318155880)
#   7318159500 unsubdivided CN-8, declarable   7318159900 CN-8 missing from the test CN-8 set, parent of 7318159910
#   7318159910 declarable, SV description only  9600000000 chapter   9617000000 heading without subdivisions, declarable
# Declarable (5): 7318155810, 7318155890, 7318159500, 7318159910, 9617000000. Never stored: the national record
# 7318155899, 7318156000 (ended before D), 7318157000 (starts after D) and the two grouping lines.
GOODS = [
    g("9617000000", "80", 0, "Vacuum flasks and other vacuum vessels, complete; parts thereof other than glass inners"),
    g("7318155890", "80", 5, "Other"),
    g("7318000000", "80", 0, "Screws, bolts, nuts, coach screws, screw hooks, rivets, cotters, cotter pins, washers "
                              "(including spring washers) and similar articles, of iron or steel"),
    goods("7318155810", "80", [("1990-01-01", 3), ("2020-01-01", 4), ("2027-01-01", 9)],
          [("1990-01-01", {"EN": "Old text", "SV": "Gammal text"}),
           ("2020-01-01", {"EN": "For use in civil aircraft", "SV": "För civila luftfartyg"}),
           ("2027-01-01", {"EN": "Future text", "SV": "Framtida text"})]),
    g("7318110000", "10", 1, "- Threaded articles"),
    g("7300000000", "80", 0, "CHAPTER 73 - ARTICLES OF IRON OR STEEL"),
    g("7318150000", "80", 2, "- - Other screws and bolts, whether or not with their nuts or washers"),
    g("7318155800", "80", 3, "- - - - With a head"),
    g("7318155880", "10", 4, "Other:"),
    g("7318155899", "80", 5, "Swedish national subdivision", national="1"),
    g("7318156000", "80", 3, "Ended before the snapshot date", end="2025-12-31"),
    g("7318157000", "80", 3, "Starts after the snapshot date", start="2027-01-01"),
    g("7318159500", "80", 3, "- - - - Other"),
    g("7318159900", "80", 3, "Fixture CN-8 that CN 2026 lacks"),
    g("7318159910", "80", 4, None),
    g("9600000000", "80", 0, "CHAPTER 96 - MISCELLANEOUS MANUFACTURED ARTICLES"),
]


# --------------------------------------------------------------------------- Measure
def comp(expr: str, amount: str | None = None, money: str | None = None, unit: str | None = None) -> dict[str, str | None]:
    return {"dutyAmount": amount, "dutyExpressionId": expr, "monetaryUnitCode": money, "measurementUnitCode": unit}


def cond(seq: str, code: str, components: tuple = (), doc: tuple[str, str] | None = None, action: str = "01",
         threshold: tuple[str, str, str] | None = None, national: str = "0") -> str:
    """A measure condition: document (type, code), price threshold (amount, currency, unit) and its duty components."""
    head = _attrs(actionCode=action, certificateCode=doc[1] if doc else None, certificateType=doc[0] if doc else None,
                  conditionCodeId=code, dutyAmount=threshold[0] if threshold else None,
                  monetaryUnitCode=threshold[1] if threshold else None, measurementUnitCode=threshold[2] if threshold else None,
                  national=national, sequenceNumber=seq)
    inner = "".join(f"<measureConditionComponent {_attrs(**c, national=national)}/>" for c in components)
    return f"<measureCondition {head}>{inner}</measureCondition>"


def measure(sid: str, code: str | None, mtype: str, geo: str, reg: tuple[str, str] = ("R8726580", "1"), start: str = "2020-01-01",
            end: str | None = None, addl: tuple[str, str] | None = None, components: tuple = (),
            stops: tuple[tuple[str, str | None], ...] = (), national: str = "0", extras: bool = False,
            conditions: tuple[str, ...] = ()) -> str:
    head = _attrs(additionalCodeId=addl[1] if addl else None, additionalCodeType=addl[0] if addl else None, dateEnd=end,
                  geographicalAreaId=geo, goodsNomenclatureCode=code, measureType=mtype, national=national, regulationId=reg[0],
                  regulationRoleType=reg[1], SID=sid, dateStart=start, stoppedFlag="0", changeType="U")
    inner = "".join(f"<measureComponent {_attrs(**c, national=national)}/>" for c in components)
    inner += "".join(conditions)
    if extras:   # a condition without a duty component and a footnote: neither changes the duty text
        inner += (cond("001", "B", doc=("Y", "999"), action="04", national=national)
                  + f"<measureFootnoteAssociation {_attrs(footnoteId='001', footnoteType='CD', national=national)}/>")
    inner += "".join(f"<measurePartialTemporaryStop {_attrs(dateStart=s, dateEnd=e, national=national, regulationId='R1400420')}/>"
                     for s, e in stops)
    return f"<measure {head}>{inner}</measure>"


AD = ("R2201910", "3")          # definitive anti-dumping regulation, effective end 2027-02-17
ENDED = ("R9000010", "1")       # base regulation whose effective end date (2026-06-30) is before D
M2 = measure("1002", "7318155810", "552", "CN", reg=AD, addl=("C", "001"), components=(comp("01", "22.0"),),
             stops=(("2014-01-20", "2014-04-22"),), extras=True)
# Kept (12): 1001-1008, 1015, 1016, and 1021-1022, whose duties sit in conditions (research R-08). Dropped: 1009 (partial stop covering D), 1010 (open-ended, regulation ended),
# 1013 (ended before D), 1014 (starts after D), -2001 (national). 1002 appears twice, identical: kept once.
# Parsed, then dropped and counted by the snapshot: 1017-1019 (Meursing table, no goods code) and 1020 (an EU measure
# on 7318155899, a code held only as a national record).
MEASURES = [
    measure("1001", "7318150000", "103", "1011", components=(comp("01", "3.7"),)),
    M2,
    measure("1003", "7318155810", "552", "CN", reg=AD, addl=("C", "999"), end="2030-06-30", components=(comp("01", "85.0"),)),
    measure("1004", "7318159500", "142", "US", reg=("R2400010", "4"), components=(comp("01", "0.0"),)),
    measure("1005", "7318000000", "478", "1011"),
    measure("1006", "7318155890", "760", "1011", reg=("X9999999", "1")),
    measure("1007", "9617000000", "103", "1011", components=(comp("17", "2.4", "EUR", "DTN"), comp("01", "6.7"),
                                                             comp("15", "1.2", "EUR", "DTN"))),
    measure("1008", "7318159910", "103", "1011", components=(comp("12"), comp("01", "4.20", "EUR", "DTN"))),
    measure("1009", "7318159500", "552", "CN", reg=AD, addl=("C", "002"), components=(comp("01", "30.0"),),
            stops=(("2026-09-01", None),)),
    measure("1010", "7318159500", "103", "1011", reg=ENDED, components=(comp("01", "2.0"),)),
    measure("-2001", "7318155810", "SEALK", "1011", reg=("22156ALK", "1"), national="1", components=(comp("01", "7.27", "SEK", "LTR"),)),
    measure("1013", "7318155810", "103", "1011", end="2025-12-31", components=(comp("01", "9.0"),)),
    measure("1014", "7318155810", "103", "CN", start="2027-01-01", components=(comp("01", "9.0"),)),
    measure("1015", "7318155800", "483", "1011"),
    measure("1016", "7318159500", "103", "1011", reg=ENDED, end="2027-12-31", components=(comp("01", "1.7"),)),
    measure("1017", None, "674", "1011", addl=("7", "040"), components=(comp("01", "9.75", "EUR", "DTN"),)),
    measure("1018", None, "672", "1011", addl=("7", "040"), components=(comp("01", "3.34", "EUR", "DTN"),)),
    measure("1019", None, "673", "1011", addl=("7", "040"), components=(comp("01", "0.0", "EUR", "DTN"),)),
    measure("1020", "7318155899", "103", "1011", components=(comp("01", "5.0"),)),
    measure("1021", "7318155890", "552", "CN", reg=AD, addl=("C", "767"), conditions=(
        cond("002", "A", (comp("01", "86.5"),)), cond("001", "A", (comp("01", "39.6"),), doc=("D", "008")))),
    measure("1022", "7318159500", "552", "CN", reg=AD, addl=("C", "123"), conditions=(
        cond("001", "F", (comp("01", "0.0", "EUR", "MIL"),), threshold=("325.0", "EUR", "MIL")),
        cond("002", "F", (comp("01", "325.0", "EUR", "MIL"),), action="11", threshold=("0.0", "EUR", "MIL")))),
    M2,
]
CONFLICT = [M2, M2.replace('dutyAmount="22.0"', 'dutyAmount="23.0"')]


# --------------------------------------------------------------------------- reference objects
def mtype(code: str, movement: str, en: str, national: str = "0") -> str:
    return (f"<measureType {_attrs(national=national, dateStart='1972-01-01', tradeMovementCode=movement, measureType=code)}>"
            f"<measureTypeDescription {_attrs(description=en, languageId='EN', national=national)}/>"
            f"<measureTypeDescription {_attrs(description='Svensk text', languageId='SV', national=national)}/></measureType>")


MEASURE_TYPES = [
    mtype("103", "0", "Third country duty"), mtype("142", "0", "Tariff preference"),
    mtype("552", "0", "Definitive anti-dumping duty"), mtype("478", "1", "Export authorization (Dual use)"),
    mtype("760", "0", "Import control"), mtype("483", "2", "Declaration of subheading submitted to legal restrictions (unit price)"),
    mtype("672", "0", "Amount of additional duty on sugar"), mtype("673", "0", "Amount of additional duty on flour"),
    mtype("674", "0", "Agricultural component"), mtype("SEALK", "0", "Alkoholskatt", national="1"),
]


def dexpr(code: str, en: str, national: str = "0") -> str:
    return (f"<dutyExpression {_attrs(dutyExpressionId=code, national=national, dateStart='1972-01-01')}>"
            f"<dutyExpressionDescription {_attrs(description=en, languageId='EN', national=national)}/></dutyExpression>")


DUTY_EXPRESSIONS = [
    dexpr("01", "% or amount"), dexpr("02", "minus % or amount"), dexpr("04", "+ % or amount"),
    dexpr("12", "+ agricultural component"), dexpr("15", "Minimum"), dexpr("17", "Maximum"), dexpr("37", "(nothing)"),
    dexpr("99", "Supplementary unit"), dexpr("AA", "Excise on beer (358)", national="1"),
]

REGULATIONS = [
    f"<baseRegulation {_attrs(datePublished='1987-09-07', officialJournalId='L 256', journalPage='1', regulationId='R8726580', regulationRoleType='1', national='0', dateStart='1988-01-01')}/>",
    f"<baseRegulation {_attrs(datePublished='2022-02-17', effectiveEndDate='2027-02-17', officialJournalId='L 36', journalPage='1', regulationId='R2201910', regulationRoleType='3', national='0', dateStart='2022-02-18')}/>",
    f"<baseRegulation {_attrs(datePublished='2021-01-01', effectiveEndDate='2026-06-30', officialJournalId='L 1', journalPage='1', regulationId='R9000010', regulationRoleType='1', national='0', dateStart='2021-01-01')}/>",
    f"<modificationRegulation {_attrs(baseRegulationId='R8726580', baseRegulationRoleType='1', modificationRegulationId='R2400010', modificationRegulationRoleType='4', datePublished='2024-01-15', officialJournalId='L 100', journalPage='5', national='0', dateStart='2024-01-16')}/>",
    f"<fullTemporaryStopRegulation {_attrs(officialJournalId='L 297', journalPage='1', ftsRegulationId='R9500010', ftsRegulationRoleType='8', national='0', datePublished='1995-12-09', dateStart='1995-11-22')}>"
    f"<fullTemporaryStopRegulationAction {_attrs(stoppedRegulationId='R9000020', stoppedRegulationRoleType='1', national='0')}/></fullTemporaryStopRegulation>",
    f"<baseRegulation {_attrs(regulationId='22156ALK', regulationRoleType='1', national='1', dateStart='2022-01-01')}/>",
]

GEO_AREAS = [
    f"<geographicalArea {_attrs(geographicalAreaId=i, national=n, SID=s, dateStart='1984-01-01')}/>"
    for i, n, s in (("1011", "0", "400"), ("CN", "0", "439"), ("US", "0", "103"), ("SE-NAT", "1", "-10013"))
]

DOCUMENTS = {
    "GoodsNomenclature": export("GoodsNomenclature", GOODS),
    "Measure": export("Measure", MEASURES),
    "MeasureType": export("MeasureType", MEASURE_TYPES),
    "GeographicalArea": export("GeographicalArea", GEO_AREAS),
    "DutyExpression": export("DutyExpression", DUTY_EXPRESSIONS),
    "Regulation": export("Regulation", REGULATIONS),
}

# The CN-8 set the loader test passes in through a small nomenclature file: 73181599 is missing on purpose.
CN2026_CN8 = ["73181558", "73181595", "96170000"]
NOMENCLATURE = [
    {"id": "hs:7318.15", "text": "Chapter 73 — Articles of iron or steel\nHeading 7318 — Screws, bolts, nuts and similar articles\n"
                                 "Subheading 7318.15 — Other screws and bolts\nCN 7318 15 58 — With a head\nCN 7318 15 95 — Other",
     "metadata": {"chapter": "73", "heading": "7318", "subheading": "7318.15", "language": "en", "source": "TARIC fixture", "edition_year": 2026}},
    {"id": "hs:9617.00", "text": "Chapter 96 — Miscellaneous manufactured articles\nHeading 9617 — Vacuum flasks\n"
                                 "Subheading 9617.00 — Vacuum flasks\nCN 9617 00 00 — Vacuum flasks",
     "metadata": {"chapter": "96", "heading": "9617", "subheading": "9617.00", "language": "en", "source": "TARIC fixture", "edition_year": 2026}},
]


# --------------------------------------------------------------------------- gpg
def find_gpg() -> str:
    gpg = os.environ.get("CARGOLINT_GPG") or shutil.which("gpg")
    if not gpg:
        raise SystemExit("gpg not found: set CARGOLINT_GPG or put gpg on PATH")
    return gpg


class GpgHome:
    """A temporary gpg home, used through the no-path invocation (cwd = the home, --homedir .)."""

    def __init__(self, gpg: str) -> None:
        self.gpg = gpg
        self.home = Path(tempfile.mkdtemp(prefix="cargolint-fixture-gpg-"))

    def run(self, *args: str, data: bytes = b"") -> bytes:
        r = subprocess.run([self.gpg, "--homedir", ".", "--batch", "--no-tty", *args], input=data, cwd=self.home,
                           capture_output=True, timeout=300)
        if r.returncode != 0:
            raise SystemExit(f"gpg {' '.join(args)} failed:\n{r.stderr.decode('utf-8', 'replace')}")
        return r.stdout

    def new_key(self, email: str) -> str:
        self.run("--pinentry-mode", "loopback", "--passphrase", "", "--quick-gen-key",
                 f"CargoLint TARIC fixture <{email}>", "ed25519", "sign", "never")
        lines = self.run("--with-colons", "--list-keys", email).decode().splitlines()
        return next(line.split(":")[9] for i, line in enumerate(lines) if line.startswith("fpr:") and lines[i - 1].startswith("pub:"))

    def public_key(self, fpr: str) -> bytes:
        return self.run("--armor", "--export", fpr)

    def sign(self, fpr: str, data: bytes) -> bytes:
        return self.run("--pinentry-mode", "loopback", "--passphrase", "", "--local-user", fpr, "--set-filename", "krypt.xml.gz",
                        "--output", "-", "--sign", data=data)

    def close(self) -> None:
        gpgconf = Path(self.gpg).with_name("gpgconf" + Path(self.gpg).suffix)
        if gpgconf.exists():
            subprocess.run([str(gpgconf), "--homedir", ".", "--kill", "all"], cwd=self.home, capture_output=True, timeout=60)
        shutil.rmtree(self.home, ignore_errors=True)


def signed_name(obj: str) -> str:
    return f"{obj}_{BATCH}_{YYMMDD}.xml.gz.pgp"


def main() -> int:
    for sub in ("xml", "extract", "keys", "bad", "conflict"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
        (OUT / sub).mkdir(parents=True)
    for obj, xml in DOCUMENTS.items():
        (OUT / "xml" / f"{obj}.xml").write_bytes(xml)
    (OUT / "conflict" / "Measure.xml").write_bytes(export("Measure", CONFLICT))
    with (OUT / "nomenclature.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for chunk in NOMENCLATURE:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    home = GpgHome(find_gpg())
    try:
        fixture_fpr = home.new_key("fixture@cargolint.invalid")
        other_fpr = home.new_key("other@cargolint.invalid")
        (OUT / "keys" / "fixture.asc").write_bytes(home.public_key(fixture_fpr))
        (OUT / "keys" / "other.asc").write_bytes(home.public_key(other_fpr))
        for obj, xml in DOCUMENTS.items():
            (OUT / "extract" / signed_name(obj)).write_bytes(home.sign(fixture_fpr, gzip.compress(xml, mtime=0)))
        mt_xml = DOCUMENTS["MeasureType"]
        tampered = bytearray((OUT / "extract" / signed_name("MeasureType")).read_bytes())
        tampered[len(tampered) // 2] ^= 0xFF
        bad = {
            "tampered": bytes(tampered),
            "other_key": home.sign(other_fpr, gzip.compress(mt_xml, mtime=0)),
            "not_gzip": home.sign(fixture_fpr, mt_xml),
            "export_id": home.sign(fixture_fpr, gzip.compress(export("MeasureType", MEASURE_TYPES, OTHER_EXPORT_ID), mtime=0)),
        }
        for variant, data in bad.items():
            (OUT / "bad" / variant).mkdir()
            (OUT / "bad" / variant / signed_name("MeasureType")).write_bytes(data)
    finally:
        home.close()

    if REAL_SIGNED.exists():
        (OUT / "real").mkdir(exist_ok=True)
        shutil.copy2(REAL_SIGNED, OUT / "real" / REAL_SIGNED.name)
    elif not (OUT / "real" / REAL_SIGNED.name).exists():
        print(f"WARNING: {REAL_SIGNED} is missing; the real-file signature test will fail", file=sys.stderr)

    expected = {
        "batch_id": BATCH, "snapshot_date": "2026-10-01", "suffix80_codes": 11, "declarable_codes": 5, "measure_records": 12,
        "cn8_mismatches": 1, "dropped_meursing": 3, "dropped_national_code": 1, "cn2026_cn8": CN2026_CN8,
        "fixture_key_fingerprint": fixture_fpr, "other_key_fingerprint": other_fpr,
    }
    (OUT / "expected.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: fixture key {fixture_fpr}, other key {other_fpr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
