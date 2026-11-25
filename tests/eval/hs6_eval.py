"""HS-6 evaluation (feature 006): the step before the CN-8 eval, from a raw goods description to the HS-6 the app picks.

    python tests/eval/hs6_eval.py --repeat 3 --tag hs6-baseline
    python tests/eval/hs6_eval.py --limit 3 --repeat 3 --dry-run     # the first three lines; prints, writes nothing
    python tests/eval/hs6_eval.py --repeat 3 --tag hs6-deepseek-v4-flash --model deepseek/deepseek-v4-flash

Live: needs OPENROUTER_API_KEY and the full knowledge base, and spends credits, so run it only when the author asks.
The set is the CN-8 eval's (tests/eval/cn8_eval_set.json, 120 EBTI rulings). A line's text is its ruling's goods
description as given, split as the app splits a typed line (tools.parsers.split_mixed: English or German text is the
English field, Chinese text the Chinese one) and not cut, as a typed line is not (an uploaded file cuts a description
at 300 characters). Its correct HS-6 is the first six digits of the ruling's CN-8, so the set needs no new labels.

Each line goes through what the app runs for a new line (agent.agent._finalize): check_descriptions, then
classify_lines for a line that is neither failed nor a pure stop word, with the context context_for_shipment builds for
an unknown shipper (hybrid search, BTI precedents, no history), then the route the store computes for it (route_line,
threshold 85, a vague line to ask the shipper, before the vague rule of 2026-11-19 only below the ask floor of 50, no
CN-8 input: the HS-6 layer's route). Leakage guard: the line's own ruling is never a BTI
precedent and never votes (ClassifyContext.exclude_refs, one line at a time); without it the ruling under test would
propose its own code with its own text. Ruling validity is judged on the set's build date, as in the CN-8 eval.

Since the HS-6 vote gate (feature 006), the route is the gate's: the vote of the 5 nearest eligible rulings at or above
the similarity floor decides, the threshold only when none votes. Each row also keeps the gate reason, the vote
(majority, share, voters, the candidate it supports) and route_by_confidence, the route the confidence rule alone gives
the same output, so that the right auto-accepts the gate loses are counted within the run.

Each row keeps the top-1 and the top 3 with their confidences, the correct HS-6, the top-1 hit, whether the correct
HS-6 is in the top 3, the description check's flag, the route, the codes the BTI precedents proposed, whether the
correct HS-6 was among the candidates shown to the model (expected_sent), and nearest_hits: the 40 rulings nearest to
the line's query vector, each with reference, HS-6, cosine distance, issuing country and whether it was eligible to
propose a code (valid on the set's date, coded to a subheading of the loaded nomenclature, not the line's own ruling);
own_rank is where the line's own ruling stands among them. The precedent search reads the nearest 12; the 40 come from
a second search with the same vector, for the log only. The results file keeps each row's nearest_hits on one line.

--repeat N runs every line N times, independently: nothing is carried over between runs, the query embedding and the
model calls are drawn anew. The entry in tests/eval/hs6_eval_history.json keeps top-1 per run, the majority top-1 (a
tie goes to the earliest run), correct-in-top-3 per run, the lines with the same top-1 and the same route in all runs,
the routes and the wrong but auto-accepted lines per run, the lines wrong in every run, the cross-layer table against
the CN-8 eval (tests/eval/cn8_eval_iteration11.json: the CN-8 step from the correct HS-6), on majority results and run
by run, whose right-right cell per run is the end-to-end estimate, and the cost. --note keeps a note with the entry.
With the gate it also keeps per run the gate reasons, the lines no ruling voted on that went to review, the right
auto-accepts, and those the gate lost against the confidence rule.

Feature 008, the precedent override: a row's fields above are the switch off, so the history stays comparable. Its vote
also keeps its counts ([[HS-6, rulings], ...], most first), from which the switch on is replayed with the routing
functions at OVERRIDE_MIN: `supported` (the model's candidate 2 or 3 the rulings' majority sits at, and whether it is the
correct HS-6) and `on` (the gate, the route, the rank and code of the HS-6 chosen, and whether it is right). The run
makes no second model call. The entry adds override_min and an `on` block with the same measures on the chosen HS-6,
its end-to-end estimate among them, the overrides that fired (each with the HS-6 it chose and whether it was right), and
how often the supported candidate was right; the report shows the switch off against on. `--replay FILE
--override-min N` replays a results file's stored answers with the switch on at another OVERRIDE_MIN, with no model
call; the replay keeps its own results file (hs6_eval.json stays the latest paid run) and a history entry marked as a
replay.

Feature 009: no line is translated; every line is searched with its raw text (rag/translate.build_queries).
`--expansion on|off` sets query expansion for the run, over CARGOLINT_QUERY_EXPANSION. `--lang zh` runs the 30 lines
of tests/eval/hs6_eval_zh.json in Chinese, each with its English line's expected HS-6 and leakage rule; `--lang en`,
the default, runs the 120 as given. The entry keeps lang and expansion.

The line-by-line results go to tests/eval/hs6_eval.json, the latest run, and to the run's own
tests/eval/hs6_eval_<tag>_<lang>_expansion-<on|off>.json (iteration<N> in place of the tag without --tag), which a run
with another tag leaves alone, as the CN-8 iteration files keep earlier CN-8 runs (feature 007).

Feature 014a: `--set coolant` runs the nine coolant lines of tests/eval/hs6_eval_coolant_set.json (the six of the
author's user test in docs/backlog.md item 10, a German line, the plain 冷却液 and, since feature 017, coolant-9, the
Chinese-only live-test line of 2026-11-20) through the same path, each line as
typed, with no leakage guard (no line is a ruling), no cross-layer table (no line has a CN-8 result) and ruling validity
on the set's build date. A line with an expected HS-6 is right when its top-1 is that code; a line expecting "ask the
shipper" when its route is ask_shipper, whatever codes it shows. Its results, history and report are its own:
tests/eval/hs6_eval_coolant.json, hs6_eval_coolant_<tag>_<lang>_expansion-<on|off>.json, hs6_eval_coolant_history.json
and hs6_eval_coolant.md; every new history entry names its set (`set`: cn8, coolant or outside). `--set outside` (the
author's decision of 2026-11-19) runs the lines of tests/eval/hs6_eval_outside_set.json, whose expected HS-6 lies
outside the twelve chapters of the old store, the same way, scored and reported as the coolant set, except that each
line's id is its source ruling's reference, which the run keeps out (leave-one-out); its files are hs6_eval_outside*.
A coolant or outside entry also keeps the precedent override's measures (`on`, at OVERRIDE_MIN), as the 120-line set's
does. `--proposal-scope nomenclature` is option (c) of that decision, evaluation only: the candidate proposal reads the
rulings of the chapters of the nomenclature search's subheadings only (each row keeps them as proposal_chapters), while
the gate's vote still reads every chapter; the app has no such setting, and the entry keeps the option.
`--vote-scope all`, the 014a regression ablation (evaluation only), runs the second vote's ruling search over every
chapter instead of the candidates' (it then equals the gate's vote and never vetoes); the entry keeps vote_scope.

Since feature 014a each row also keeps vote_chapters and not_indexed (the line's ruling scope), vote_hits (the rulings
of the second vote's search, within the candidates' chapters, each once at its highest similarity, nearest first, with
whether it was eligible whatever the floor), customs_wording (the rewrite searched with) and citation_notes (per
candidate code). nearest_hits stay those of the precedent search over every chapter, which the gate's vote reads (rule
(a)). `--customs-wording on|off` sets the switch for the run, over CARGOLINT_CUSTOMS_WORDING; the entry keeps it with
the run's floor, and the run's own file name ends in _wording-<on|off>. `--replay FILE --floor X` rebuilds every row's
votes at the floor X, the gate's from its nearest_hits and the second from its vote_hits, with the routing functions
and no model call (`--override-min` combines with it): exact, and evidence for a new floor, only at or above the run's
own floor and for a run with query expansion and customs wording off (one query vector per line, so the 12 nearest of
nearest_hits are the gate's rulings); any other replay is marked not exact, with the reason. The replay belongs to the
set its file names, keeps its own results file and adds
an entry marked `replay` to that set's history and report.

--model names another OpenRouter chat model for this run only (the default is the configured CARGOLINT_CHAT_MODEL,
Gemini 2.5 Flash since feature 006; the entry keeps the model and the reasoning sent next to its tag), through
tests/eval/cn8_eval.run_settings: thinking stays off ({"enabled": false}; "minimal" still thinks) unless the model has no
reasoning parameter, and a model missing from the price table gets its OpenRouter list price for the cost tally.
Structured output stays JSON-schema with require_parameters. The product retries an answer that is not valid JSON once and a wrong
schema twice; a --model run retries a wrong schema once too. A call still invalid fails its line, not the run. Each run
counts the invalid answers, the unparseable ones among them, the retries and the failed calls. Each row keeps raw_confidence, the model's
own confidence of the top-1 before the vague cap, and the entry its distribution over right and wrong top-1 results.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from agent.config import (ASK_FLOOR, DEFAULT_THRESHOLD, HS6_VOTE_K, HS6_VOTE_MIN_SIMILARITY, HS6_VOTE_SHARE,  # noqa: E402
                          OVERRIDE_MIN, RETRIEVAL_K, get_settings)
from agent.llm import get_client, set_client_factory  # noqa: E402
from agent.routing import SchemaError, hs6_choice, hs6_gate, hs6_ruling_vote, route_line  # noqa: E402
from agent.schemas import FlagKind, Hs6Vote, LineStatus, RankOut, SourceKind, Usage  # noqa: E402
from rag.loader import open_knowledge_base  # noqa: E402
from rag.retriever import DISTANCE_DECIMALS, stable_order  # noqa: E402
from rag.translate import clear_cache as clear_expansions  # noqa: E402
from tests.eval.cn8_eval import (OverriddenClient, dump_results, expected_sent_share, majority, price_for_run,  # noqa: E402
                                 run_settings)
from tools.check_description import check_descriptions  # noqa: E402
import tools.classify_hs6 as classify_tool  # noqa: E402
from tools.classify_hs6 import ClassifyContext, classify_lines  # noqa: E402
from tools.common import LineText, run_per_line  # noqa: E402
from tools.parsers import split_mixed  # noqa: E402

SET = ROOT / "tests" / "eval" / "cn8_eval_set.json"
ZH_SET = ROOT / "tests" / "eval" / "hs6_eval_zh.json"   # feature 009: 30 of the set's lines written in Chinese
OUT = ROOT / "tests" / "eval" / "hs6_eval.json"
HISTORY = ROOT / "tests" / "eval" / "hs6_eval_history.json"
REPORT = ROOT / "tests" / "eval" / "hs6_eval.md"
CN8_RESULTS = ROOT / "tests" / "eval" / "cn8_eval_iteration11.json"
COOLANT_SET = ROOT / "tests" / "eval" / "hs6_eval_coolant_set.json"   # feature 014a: the nine coolant lines
COOLANT_OUT = ROOT / "tests" / "eval" / "hs6_eval_coolant.json"
COOLANT_HISTORY = ROOT / "tests" / "eval" / "hs6_eval_coolant_history.json"
COOLANT_REPORT = ROOT / "tests" / "eval" / "hs6_eval_coolant.md"
OUTSIDE_SET = ROOT / "tests" / "eval" / "hs6_eval_outside_set.json"   # feature 014a (2026-11-19): outside the twelve
OUTSIDE_OUT = ROOT / "tests" / "eval" / "hs6_eval_outside.json"
OUTSIDE_HISTORY = ROOT / "tests" / "eval" / "hs6_eval_outside_history.json"
OUTSIDE_REPORT = ROOT / "tests" / "eval" / "hs6_eval_outside.md"
FAMILIES = ROOT / "tests" / "eval" / "hs6_eval_families.json"   # backlog items 20/21: the 120-line set's near-duplicate families
TYPED_SETS = ("coolant", "outside")   # sets of typed lines, scored and reported as the coolant set
HITS_LOGGED = 40
SEARCHED = 2 * RETRIEVAL_K    # the rulings precedent_codes reads per query vector
QUADRANTS = ("hs6_right_cn8_right", "hs6_right_cn8_wrong", "hs6_wrong_cn8_right", "hs6_wrong_cn8_wrong")
GATES = ("vote_agrees", "vote_disagrees", "vote_tie", "vote_share_low", "scoped_veto", "no_rulings",   # not_gated:
         "not_gated")   # flagged, failed, no candidate; scoped_veto: the second vote sent the line to review (014a, rule (a))
OTHER_MODEL_RETRIES = 1        # a --model run retries an invalid answer once; the product retries MAX_SCHEMA_RETRIES times
TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")   # a tag names the run's own results file
_rec = threading.local()       # per worker thread, for the line in hand: the logged ruling searches


def expected_hs6(ruling: dict) -> str:
    """The correct HS-6 of an eval line: the first six digits of its ruling's CN-8, dotted as the nomenclature is."""
    return f"{ruling['cn8'][:4]}.{ruling['cn8'][4:6]}"


def expected_of(item: dict) -> str | None:
    """A line's correct HS-6: a coolant line's expected_hs6, None for one that expects "ask the shipper" (feature 014a);
    else the first six digits of its ruling's CN-8."""
    if "expected_hs6" in item or "expected_route" in item:
        return item.get("expected_hs6")
    return expected_hs6(item)


def level_hit(top1: str | None, expected: str | None, level: int) -> bool:
    """Whether `top1` matches `expected` to `level` digits (2 = chapter, 4 = heading)."""
    return bool(top1 and expected and top1[:level] == expected[:level])


def miss_level(top1: str | None, expected: str | None) -> str | None:
    """Where a wrong line missed: "chapter", "heading" or "subheading"; None if right or without a code."""
    if not top1 or not expected or top1 == expected:
        return None
    if top1[:2] != expected[:2]:
        return "chapter"
    if top1[:4] != expected[:4]:
        return "heading"
    return "subheading"


def load_families() -> dict[str, list[str]]:
    """Backlog items 20/21: family name -> member references, from hs6_eval_families.json."""
    data = json.loads(FAMILIES.read_text(encoding="utf-8"))
    return {family["name"]: [m["reference"] for m in family["members"]] for family in data["families"]}


def family_siblings(members: dict[str, list[str]]) -> dict[str, frozenset[str]]:
    """Reference -> its family's other references, so a family member's exclusion keeps every sibling out."""
    out: dict[str, frozenset[str]] = {}
    for refs in members.values():
        group = frozenset(refs)
        for r in refs:
            out[r] = group - {r}
    return out


def coolant_items(data: dict) -> list[dict]:
    """Feature 014a: the coolant set's lines as run_once takes them: the id as the reference, the text as the
    description, and the expected HS-6 or route."""
    return [{"reference": line["id"], "chapter": (line.get("expected_hs6") or "")[:2], "language": "",
             "description": line["text"], **{k: line[k] for k in ("expected_hs6", "expected_route") if k in line}}
            for line in data["lines"]]


def coolant_score(row: dict, item: dict) -> dict:
    """Feature 014a (spec User Story 1, scenario 1): a coolant row's expected route and whether it is right: a line with
    an expected HS-6 on its top-1, a line expecting "ask the shipper" on its route, whatever codes it shows."""
    route = item.get("expected_route")
    return {"expected_route": route, "right": row["route"] == route if route else bool(row["hit"])}


def line_text(line_no: int, ruling: dict) -> LineText:
    """The ruling's goods description as the app takes a typed line: split into Chinese and other text, not cut."""
    zh, en = split_mixed(ruling["description"])
    return LineText(line_no=line_no, text_zh=zh, text_en=en)


def _logged(search: Any, unscoped: bool = False) -> Any:
    """search_by_vector as the app calls it, unchanged; for the calling thread's line it also keeps the HITS_LOGGED
    rulings nearest to the same vector, from a second search (the log only). Feature 014a: the vote's search within
    the candidates' chapters (the one with a chapter filter) is kept as the product read it, apart, for vote_hits. With
    `unscoped` (the 014a regression ablation, eval only) that search runs over every chapter, as the vote did before
    feature 014a, and is still kept as the vote's rulings."""
    def wrapper(vector: list[float], k: int, chapter_filter: list[str] | None = None, where: dict | None = None) -> Any:
        hits = search(vector, k, None if unscoped else chapter_filter, where)
        searches = getattr(_rec, "searches", None)
        if searches is not None and chapter_filter:
            _rec.vote_searches.append(hits)
        elif searches is not None:
            searches.append(search(vector, HITS_LOGGED, chapter_filter, where))
        return hits
    return wrapper


def _nomenclature_logged(search: Any) -> Any:
    """Option (c) (feature 014a, 2026-11-19, eval only): the nomenclature search as the app calls it, unchanged; for the
    calling thread's line it keeps the chapters of the subheadings its first unfiltered search returned."""
    def wrapper(queries: list[str], chapter_filter: list[str] | None = None, *args: Any, **kwargs: Any) -> Any:
        chunks, trace = search(queries, chapter_filter, *args, **kwargs)
        if chapter_filter is None and getattr(_rec, "proposal_chapters", ()) is None:
            _rec.proposal_chapters = sorted({c.code[:2] for c in chunks})
        return chunks, trace
    return wrapper


def _proposal_in(original: Any) -> Any:
    """Option (c), eval only: precedent_codes over a ruling search within the chapters of the line's nomenclature
    subheadings, by the index's own search (not the run's log), as deep as the app's proposal (2 × k per query vector),
    in place of the hits over every chapter, which the gate's vote still reads."""
    def wrapper(bti_vectors: Any, bti_store: Any, query_vectors: list[list[float]], *args: Any, hits: Any = None,
                k: int = RETRIEVAL_K, **kwargs: Any) -> Any:
        chapters = getattr(_rec, "proposal_chapters", None)
        search = type(bti_vectors).search_by_vector
        scoped = [search(bti_vectors, vec, k * 2, chapters) for vec in query_vectors] if chapters else []
        return original(bti_vectors, bti_store, query_vectors, *args, hits=scoped, k=k, **kwargs)
    return wrapper


def nearest_hits(searches: list[list[tuple[str, float]]], own: str, kb: Any, as_of: date) -> list[dict]:
    """The rulings nearest to a line's query vectors, each once at its smallest cosine distance, nearest first (equal
    distances by id, as rag.retriever.stable_order), at most HITS_LOGGED, with what the store says about each."""
    best: dict[str, float] = {}
    for hits in searches:
        for doc_id, score in hits:
            best[doc_id] = min(best.get(doc_id, float("inf")), 1.0 - score)
    out = []
    for doc_id in sorted(best, key=lambda d: (round(best[d], DISTANCE_DECIMALS), d))[:HITS_LOGGED]:
        record = kb.bti.get(doc_id) or {}
        reference, code = doc_id.removeprefix("bti:"), record.get("code") or ""
        out.append({"reference": reference, "hs6": code, "distance": round(best[doc_id], 6),
                    "country": record.get("member_state") or "",
                    "eligible": (reference != own and bool(code) and kb.index.get(code) is not None
                                 and kb.bti.get(doc_id, as_of) is not None)})
    return out


def vote_hits(searches: list[list[tuple[str, float]]], own: str | None, kb: Any, as_of: date) -> list[dict]:
    """Feature 014a: the rulings the vote's search within the candidates' chapters returned, each once at its highest
    similarity, nearest first as hs6_voters orders them (rag.retriever.stable_order), with whether it could vote
    whatever the floor: valid on the day, coded to a subheading of the loaded nomenclature, not the line's own ruling. A
    replay applies a floor to them (floor_fields)."""
    best: dict[str, float] = {}
    for hits in searches:
        for doc_id, score in hits:
            best[doc_id] = max(best.get(doc_id, float("-inf")), score)
    out = []
    for doc_id in stable_order(list(best.items())):
        record = kb.bti.get(doc_id) or {}
        reference, code = doc_id.removeprefix("bti:"), record.get("code") or ""
        out.append({"reference": reference, "hs6": code, "similarity": round(best[doc_id], 6),
                    "eligible": (reference != own and bool(code) and kb.index.get(code) is not None
                                 and kb.bti.get(doc_id, as_of) is not None)})
    return out


def vote_fields(vote: Hs6Vote | None) -> dict | None:
    """A row's vote: its majority, share, voters, the candidate it supports, and its counts ([[HS-6, rulings], ...])."""
    return None if vote is None else {"majority": vote.majority, "share": vote.majority_share,
                                      "voters": sum(len(c) for _, c in vote.competing), "candidate": vote.candidate,
                                      "counts": [[code, len(c)] for code, c in vote.competing]}


def count_invalid(client: Any) -> Counter:
    """Count, on `client` (a StructuredCaller), the answers it rejects: those that are not valid JSON (the raw client's
    {"_invalid": ...}) and those that do not match the schema, and the calls still invalid after their last retry
    (SchemaError: the line fails, the run goes on). Returns the live counter; the caller's behaviour stays as it is."""
    counts: Counter = Counter()
    lock = threading.Lock()
    raw_structured, call = client.raw.raw_structured, client.call

    def answered(schema: Any, system: str, user: str) -> Any:
        out = raw_structured(schema, system, user)
        kind = None
        if isinstance(out, dict) and out.get("_invalid"):
            kind = "unparseable"
        elif not isinstance(out, schema):
            try:
                schema.model_validate(out)
            except ValidationError:
                kind = "schema_invalid"
        if kind:
            with lock:
                counts[kind] += 1
        return out

    def called(schema: Any, system: str, user: str, max_retries: int | None = None) -> Any:
        try:
            return call(schema, system, user, max_retries)
        except SchemaError:
            with lock:
                counts["failed"] += 1
            raise

    client.raw.raw_structured, client.call = answered, called
    return counts


def parse_counts(counts: Counter, rows: list[dict]) -> dict:
    """One run's invalid answers: each is retried unless its call failed, so the retries are the invalid answers less the
    failed calls; failed_lines are the rows whose check or HS-6 step failed for any reason."""
    invalid = counts["unparseable"] + counts["schema_invalid"]
    return {"retries": invalid - counts["failed"], "unparseable": counts["unparseable"],
            "schema_invalid": counts["schema_invalid"], "failed_calls": counts["failed"],
            "failed_lines": sum(r["status"] == "failed" for r in rows)}


def _ranking(call: Any) -> Any:
    """client.call, also keeping for the calling thread's line the ranking the model returned, as _rec.rank."""
    def wrapper(schema: Any, system: str, user: str, *args: Any, **kwargs: Any) -> Any:
        result = call(schema, system, user, *args, **kwargs)
        if schema is RankOut:
            _rec.rank = result
        return result
    return wrapper


def confidence_table(runs: list[list[dict]]) -> dict[str, dict[str, int]]:
    """The model's own confidence of its top-1 (before the vague cap) over all runs, highest first: how many top-1
    results at each value were right and wrong. Rows without a top-1 are left out."""
    table: dict[int, Counter] = {}
    for run in runs:
        for r in run:
            value = r.get("raw_confidence", r["confidence"])
            if r["top1"] is not None and value is not None:
                table.setdefault(value, Counter())["right" if r["hit"] else "wrong"] += 1
    return {str(v): {"right": c["right"], "wrong": c["wrong"]} for v, c in sorted(table.items(), reverse=True)}


def eval_rulings(data: dict, lang: str) -> list[dict]:
    """Feature 009: the set's rulings in the run's language. "en": the 120 as given. "zh": the 30 of hs6_eval_zh.json,
    each its ruling with the Chinese text as the description, so the expected codes and the leakage rule (the line's
    own ruling) are the English line's."""
    if lang == "en":
        return data["rulings"]
    by_ref = {r["reference"]: r for r in data["rulings"]}
    return [{**by_ref[z["ref"]], "description": z["text_zh"]}
            for z in json.loads(ZH_SET.read_text(encoding="utf-8"))["lines"]]


def results_name(base: str, lang: str, expansion: bool, wording: bool | None = None) -> str:
    """Feature 009: a run's own results file names its language and its query expansion; feature 014a: and the
    customs-wording switch, when given."""
    name = f"{base}_{lang}_expansion-{'on' if expansion else 'off'}"
    return name if wording is None else f"{name}_wording-{'on' if wording else 'off'}"


def run_once(rulings: list[dict], kb: Any, client: Any, as_of: date, workers: int, expansion: bool = False,
             leave_one_out: bool = True, customs_wording: bool = False,
             vote_scope: str = "candidates", proposal_scope: str = "all",
             family_exclusion: bool = False, siblings: dict[str, frozenset[str]] | None = None) -> tuple[list[dict], float]:
    """One pass of the app's HS-6 path over the set: one row per ruling, and the elapsed seconds. `leave_one_out` keeps
    each line's own ruling out; the coolant set has none (feature 014a). `customs_wording` is the switch for the run.
    `vote_scope` "all" runs the vote over every chapter instead of the candidates' (the 014a regression ablation, eval
    only: the app is unchanged). `proposal_scope` "nomenclature" is option (c) (2026-11-19, eval only): the candidate
    proposal reads the rulings of the chapters of the nomenclature search's subheadings only. `family_exclusion`
    (backlog item 21) keeps a family member's siblings out too, from `siblings`."""
    clear_expansions()   # an independent run: no query expansion and no rewrite carried over
    lines = [line_text(i, r) for i, r in enumerate(rulings, start=1)]
    base = ClassifyContext(hybrid=True, as_of=as_of, expansion=expansion,   # context_for_shipment for an unknown
                           customs_wording=customs_wording)                 # shipper, on the set's date
    t0 = time.perf_counter()
    checks = check_descriptions(lines, kb.rules, client, workers)
    todo = []
    for line, r, chk in zip(lines, rulings, checks):   # what store.update_check and select_lines pass on
        if chk.flag is not None and not chk.flag.pure_stop_word:
            line.flag_kind, line.flag_reason = chk.flag.kind.value, chk.flag.reason
            todo.append((line, r["reference"]))

    recorder = SimpleNamespace(call=_ranking(client.call))

    def one(item: tuple[LineText, str]) -> tuple[Any, list, list, Any]:
        line, reference = item
        _rec.searches, _rec.vote_searches, _rec.rank, _rec.proposal_chapters = [], [], None, None
        excluded = frozenset({reference}) if leave_one_out else None   # the leakage guard: never the line's own ruling
        if family_exclusion and excluded is not None and siblings:
            own_siblings = siblings.get(reference)
            if own_siblings:
                excluded = frozenset({reference}) | own_siblings      # backlog item 21: a family member's siblings too
        ctx = replace(base, exclude_refs=excluded)
        return (classify_lines([line], ctx, kb, recorder, workers=1)[0], _rec.searches, _rec.vote_searches, _rec.rank,
                _rec.proposal_chapters)

    vectors = getattr(kb, "bti_vectors", None)
    own = vectors is not None and "search_by_vector" in vars(vectors)
    if vectors is not None:
        search = vectors.search_by_vector
        vectors.search_by_vector = _logged(search, unscoped=vote_scope == "all")   # the instance only, for this run
    scoped_proposal = proposal_scope == "nomenclature"                              # option (c), for this run only
    if scoped_proposal:
        retriever, proposal = kb.retriever, classify_tool.precedent_codes
        own_search = "search" in vars(retriever)
        nomenclature = retriever.search
        retriever.search = _nomenclature_logged(nomenclature)
        classify_tool.precedent_codes = _proposal_in(proposal)
    try:
        done = run_per_line(todo, one, lambda item, exc: None, workers=workers)
    finally:
        if vectors is not None:
            if own:
                vectors.search_by_vector = search
            else:
                del vectors.search_by_vector
        if scoped_proposal:
            classify_tool.precedent_codes = proposal
            if own_search:
                retriever.search = nomenclature
            else:
                del retriever.search
    elapsed = time.perf_counter() - t0
    classified = {line.line_no: res for (line, _), res in zip(todo, done)}
    rows = []
    for line, r, chk in zip(lines, rulings, checks):
        res = classified.get(line.line_no)
        cls, searches, scoped, rank, proposal_chapters = res if res is not None else (None, [], [], None, None)
        if chk.status == LineStatus.failed:
            status, error = LineStatus.failed, chk.error_reason
        elif line.line_no not in classified:       # a pure stop word: checked, nothing to classify
            status, error = LineStatus.checked, None
        elif cls is None:
            status, error = LineStatus.failed, "timed out"
        else:
            status, error = cls.status, cls.error_reason
        expected = expected_of(r)
        candidates = cls.candidates if cls is not None else []
        codes = [c.code for c in candidates]
        conf = candidates[0].confidence if candidates else None
        kind = chk.flag.kind if chk.flag is not None else None
        flagged = kind is not None and kind != FlagKind.ok
        vote = cls.hs6_vote if cls is not None else None                 # the gate's vote, over every chapter
        second = cls.hs6_scoped_vote if cls is not None else None        # feature 014a (rule (a)): the second vote
        scope = cls.ruling_scope if cls is not None else None
        route, _ = route_line(kind, conf, status, flagged, DEFAULT_THRESHOLD, ASK_FLOOR, hs6_vote=vote,
                              hs6_scoped_vote=second)
        by_confidence, _ = route_line(kind, conf, status, flagged, DEFAULT_THRESHOLD, ASK_FLOOR)   # before the vote gate
        gated = status == LineStatus.checked and kind == FlagKind.ok and (conf or 0) > 0          # as the store sets hs6_gate
        shown = {s.id for s in cls.sources if s.kind == SourceKind.nomenclature} if cls is not None else set()
        hits = nearest_hits(searches, r["reference"], kb, as_of)
        rows.append({
            "reference": r["reference"], "chapter": r["chapter"], "language": r["language"], "expected": expected,
            "flag": kind.value if kind is not None else "failed", "top1": codes[0] if codes else None, "top3": codes[:3],
            "confidences": [c.confidence for c in candidates[:3]], "confidence": conf,
            "raw_confidence": (next((c.confidence for c in rank.candidates if c.code == codes[0]), None)
                               if rank is not None and codes else None),
            "raw": [{"code": c.code, "confidence": c.confidence} for c in rank.candidates] if rank is not None else None,
            "hit": bool(codes) and codes[0] == expected, "in_top3": expected in codes[:3], "route": route.value,
            "route_by_confidence": by_confidence.value,
            "gate": hs6_gate(conf, DEFAULT_THRESHOLD, vote, None, second)[1].value if gated else "not_gated",
            "vote": vote_fields(vote), "scoped_vote": vote_fields(second),
            "status": status.value, "error": error,
            "precedent_codes": cls.retrieval_trace.precedent_codes if cls is not None and cls.retrieval_trace else [],
            "expected_sent": f"hs:{expected}" in shown,
            "own_rank": next((k for k, h in enumerate(hits, start=1) if h["reference"] == r["reference"]), None),
            "nearest_hits": hits,
            # feature 014a: the chapters the second vote searched and its rulings (for a replay at another floor), the
            # rewrite searched with, and the citation notes per candidate
            "vote_chapters": scope.chapters if scope is not None else [],
            "not_indexed": scope.not_indexed if scope is not None else [],
            "vote_hits": vote_hits(scoped, r["reference"] if leave_one_out else None, kb, as_of),
            "customs_wording": cls.customs_wording.text if cls is not None and cls.customs_wording else None,
            "proposal_chapters": proposal_chapters,   # option (c): the chapters the proposal read; None as the app runs
            "citation_notes": [{"code": c.code, "notes": [n.model_dump() for n in c.citation_notes]}
                               for c in candidates if c.citation_notes]})
        rows[-1].update(override_fields(rows[-1]))   # feature 008: the switch on, from the same answers
        if "expected_hs6" in r or "expected_route" in r:
            rows[-1].update(coolant_score(rows[-1], r))   # feature 014a: a coolant line, right on its code or its route
    return rows, elapsed


def replay_vote(row: dict, field: str = "vote") -> Hs6Vote | None:
    """Feature 008: a row's vote as the routing functions take it, rebuilt from its counts by the product's own vote
    (the rulings' countries do not route); `field` "scoped_vote" is the second vote of rule (a) (feature 014a), None in
    a row from before it."""
    v = row.get(field)
    if v is None:
        return None
    return hs6_ruling_vote([(code, "") for code, k in v["counts"] for _ in range(k)], row["top3"])


def override_fields(row: dict, override_min: int = OVERRIDE_MIN) -> dict:
    """Feature 008: a row's `supported` and `on` fields, from what it keeps (its flag, status, confidence, top 3 and vote
    counts) through the routing functions with the switch on at `override_min`; its other fields stay the switch off."""
    vote, scoped = replay_vote(row), replay_vote(row, "scoped_vote")
    kind = None if row["flag"] == "failed" else FlagKind(row["flag"])
    conf = row["confidence"]
    route, _ = route_line(kind, conf, row["status"], kind not in (None, FlagKind.ok), DEFAULT_THRESHOLD, ASK_FLOOR,
                          hs6_vote=vote, hs6_override_min=override_min, hs6_scoped_vote=scoped)
    gated = row["status"] == LineStatus.checked.value and kind == FlagKind.ok and (conf or 0) > 0   # as run_once
    gate = hs6_gate(conf, DEFAULT_THRESHOLD, vote, override_min, scoped)[1] if gated else None
    rank, chosen = hs6_choice([SimpleNamespace(code=code) for code in row["top3"]], vote, gate)
    supported = vote.candidate if vote is not None else None
    return {"supported": {"rank": supported, "right": row["top3"][supported - 1] == row["expected"] if supported else None},
            "on": {"gate": gate.value if gate is not None else "not_gated", "route": route.value, "rank": rank,
                   "chosen": chosen, "hit": chosen is not None and chosen == row["expected"]}}


def floor_fields(row: dict, floor: float, override_min: int = OVERRIDE_MIN) -> dict:
    """Feature 014a: a row as the product would have routed it at the similarity floor `floor`, under rule (a): the
    gate's vote rebuilt from its nearest_hits (the 5 nearest eligible ones at or above the floor among the 12 the
    unfiltered search read) and the second vote from its vote_hits (the search within the candidates' chapters), each by
    the product's vote, then the gate and the route, the switch on at `override_min` and, for the coolant set, the score;
    its other fields are the run's. Exact for a floor at or above the run's, and for a run with one query vector per
    line (query expansion and customs wording off): the product would have read the same rulings."""
    nearest = [(h["hs6"], "") for h in row["nearest_hits"][:SEARCHED]
               if h["eligible"] and 1 - h["distance"] >= floor][:HS6_VOTE_K]
    voters = [(h["hs6"], "") for h in row["vote_hits"] if h["eligible"] and h["similarity"] >= floor]
    vote = hs6_ruling_vote(nearest, row["top3"]) if row["top3"] else None
    scoped = hs6_ruling_vote(voters, row["top3"]) if row["top3"] else None
    kind = None if row["flag"] == "failed" else FlagKind(row["flag"])
    conf = row["confidence"]
    route, _ = route_line(kind, conf, row["status"], kind not in (None, FlagKind.ok), DEFAULT_THRESHOLD, ASK_FLOOR,
                          hs6_vote=vote, hs6_scoped_vote=scoped)
    gated = row["status"] == LineStatus.checked.value and kind == FlagKind.ok and (conf or 0) > 0   # as run_once
    out = {**row, "vote": vote_fields(vote), "scoped_vote": vote_fields(scoped), "route": route.value,
           "gate": hs6_gate(conf, DEFAULT_THRESHOLD, vote, None, scoped)[1].value if gated else "not_gated"}
    out.update(override_fields(out, override_min))
    if "right" in row:                                 # the coolant set
        expected = {"expected_route": row["expected_route"]} if row.get("expected_route") else {"expected_hs6": row["expected"]}
        out.update(coolant_score(out, expected))
    return out


def _seen(r: dict) -> dict:
    return {"top1": r["top1"], "confidence": r["confidence"], "route": r["route"], "in_top3": r["in_top3"]}


def measures(runs: list[list[dict]]) -> dict:
    """The HS-6 layer over N runs of the same lines; `runs` holds each run's rows in set order. Chapter (2-digit) and
    heading (4-digit) accuracy are per run and on the majority's full HS-6 code, truncated after the majority is chosen."""
    n = len(runs[0])
    same_top1 = same_route = majority_hits = 0
    majority_chapter = majority_heading = 0
    wrong_levels: Counter = Counter()
    always_wrong, unstable = [], []
    for seen in zip(*runs):
        codes = [r["top1"] for r in seen]
        expected = seen[0]["expected"]
        chosen = majority(codes)                                            # the majority's full HS-6 code first
        same_top1 += len(set(codes)) == 1
        same_route += len({r["route"] for r in seen}) == 1
        majority_hits += chosen == expected
        majority_chapter += level_hit(chosen, expected, 2)
        majority_heading += level_hit(chosen, expected, 4)
        if (level := miss_level(chosen, expected)) is not None:
            wrong_levels[level] += 1
        line = {"reference": seen[0]["reference"], "chapter": seen[0]["chapter"], "expected": seen[0]["expected"],
                "seen": [_seen(r) for r in seen]}
        if not any(r["hit"] for r in seen):
            always_wrong.append(line)
        if len(set(codes)) > 1:
            unstable.append(line)
    return {"top1_runs": [sum(r["hit"] for r in run) for run in runs], "majority_top1": majority_hits,
            "top3_runs": [sum(r["in_top3"] for r in run) for run in runs],
            "chapter_runs": [sum(level_hit(r["top1"], r["expected"], 2) for r in run) for run in runs],
            "heading_runs": [sum(level_hit(r["top1"], r["expected"], 4) for r in run) for run in runs],
            "majority_chapter": majority_chapter, "majority_heading": majority_heading,
            "wrong_levels": dict(wrong_levels),
            "same_top1": same_top1, "top1_consistency": round(same_top1 / n, 4),
            "same_route": same_route, "route_consistency": round(same_route / n, 4),
            "routes_runs": [{route: sum(r["route"] == route for r in run) for route in ("auto_accept", "review", "ask_shipper")}
                            for run in runs],
            "wrong_auto_runs": [[{"reference": r["reference"], "expected": r["expected"], "top1": r["top1"],
                                  "confidence": r["confidence"]} for r in run if r["route"] == "auto_accept" and not r["hit"]]
                                for run in runs],
            "always_wrong": always_wrong, "unstable": unstable}


def family_measures(runs: list[list[dict]], members: dict[str, list[str]]) -> dict:
    """Backlog item 21: the family-aware majority alongside the per-line one. Each family counts once, scored as the
    fraction of its lines right (by majority, full HS-6); each standalone line counts once. 85 standalone lines plus
    12 families = 97 units."""
    majority_right: dict[str, bool] = {}
    for seen in zip(*runs):
        codes = [r["top1"] for r in seen]
        majority_right[seen[0]["reference"]] = majority(codes) == seen[0]["expected"]
    in_runs = set(majority_right)
    per_family = {}
    for name, refs in members.items():
        present = [r for r in refs if r in in_runs]
        if present:
            per_family[name] = sum(majority_right[r] for r in present) / len(present)
    family_refs = {r for refs in members.values() for r in refs}
    standalone = sum(majority_right[r] for r in in_runs if r not in family_refs)
    units = sum(per_family.values()) + standalone
    return {"family_majority": round(units, 4),
            "family_units": len(per_family) + sum(1 for r in in_runs if r not in family_refs),
            "per_family": per_family, "standalone": standalone}


def gate_measures(runs: list[list[dict]]) -> dict:
    """The vote gate run by run: its reasons, the lines no ruling voted on that went to review, the right auto-accepts,
    and the right lines the confidence rule alone would have auto-accepted that the gate did not (lost)."""
    return {"gate_runs": [{g: sum(r["gate"] == g for r in run) for g in GATES} for run in runs],
            "no_rulings_review_runs": [sum(r["gate"] == "no_rulings" and r["route"] == "review" for r in run) for run in runs],
            "no_voter_runs": [sum(r["top1"] is not None and r.get("vote") is None for r in run) for run in runs],   # 014a
            "right_auto_runs": [sum(r["hit"] and r["route"] == "auto_accept" for r in run) for run in runs],
            "lost_runs": [sum(r["hit"] and r["route_by_confidence"] == "auto_accept" and r["route"] != "auto_accept"
                              for r in run) for run in runs]}


def coolant_measures(runs: list[list[dict]]) -> dict:
    """Feature 014a: the coolant set over N runs (spec FR-004): right per run, the lines right on majority (a line's most
    frequent top-1, or route for a line expecting "ask the shipper", a tie going to the earliest run), the expected
    HS-6 in the top 3 per run (lines with one only), the routes, the wrong auto-accepts (auto-accepted and not right)
    and each line's outcome per run and on majority."""
    lines = []
    for seen in zip(*runs):
        first = seen[0]
        expected = first["expected_route"] or first["expected"]
        found = majority([r["route"] if first["expected_route"] else r["top1"] for r in seen])
        lines.append({"id": first["reference"], "expected": expected, "majority": found, "right": found == expected,
                      "seen": [{"top1": r["top1"], "route": r["route"]} for r in seen]})
    return {"top1_runs": [sum(r["right"] for r in run) for run in runs],
            "majority_top1": sum(line["right"] for line in lines),
            "top3_runs": [sum(r["in_top3"] for r in run) for run in runs],
            "routes_runs": [{route: sum(r["route"] == route for r in run) for route in ("auto_accept", "review", "ask_shipper")}
                            for run in runs],
            "wrong_auto_runs": [[{"reference": r["reference"], "expected": r["expected_route"] or r["expected"],
                                  "top1": r["top1"], "confidence": r["confidence"]}
                                 for r in run if r["route"] == "auto_accept" and not r["right"]] for run in runs],
            "lines": lines}


def typed_on_measures(runs: list[list[dict]]) -> dict:
    """Feature 014a: a coolant or outside set's runs with the precedent override on: each row's `on` route and HS-6 in
    place of its own, scored again (a coded line on its HS-6, an "ask the shipper" line on its route)."""
    on = [[{**r, "right": r["route"] == r["expected_route"] if r["expected_route"] else r["hit"]} for r in on_rows(run)]
          for run in runs]
    m = coolant_measures(on)
    return {key: m[key] for key in ("top1_runs", "majority_top1", "routes_runs", "wrong_auto_runs")}


def typed_measures(runs: list[list[dict]], override_min: int = OVERRIDE_MIN) -> dict:
    """Feature 014a: a coolant or outside entry's measures: the switch off, the vote gate's, and the switch on at
    `override_min` when the rows keep it (every row since feature 008 does)."""
    m = {**coolant_measures(runs), **gate_measures(runs), "override_min": override_min}
    if all("on" in r for run in runs for r in run):
        m["on"] = typed_on_measures(runs)
    return m


def own_ruling(runs: list[list[dict]]) -> dict:
    """Run by run, how many lines had their own ruling nearest, among the rulings the precedent search reads, and among
    the logged ones: what the leakage guard keeps out."""
    return {"nearest_runs": [sum(r["own_rank"] == 1 for r in run) for run in runs],
            "searched_runs": [sum(r["own_rank"] is not None and r["own_rank"] <= SEARCHED for r in run) for run in runs],
            "logged_runs": [sum(r["own_rank"] is not None for r in run) for run in runs], "searched": SEARCHED}


def replay_runs(report: dict, override_min: int) -> list[list[dict]]:
    """Feature 008: a results file's runs with the switch on recomputed at `override_min` from each row's stored
    answers (override_fields); nothing else changes."""
    return [[{**r, **override_fields(r, override_min)} for r in run] for run in (report.get("runs") or [report["rows"]])]


def entry_measures(runs: list[list[dict]], cn8: dict[str, dict], cn8_data: dict, cn8_path: str,
                   override_min: int = OVERRIDE_MIN) -> tuple[dict, dict]:
    """The history entry's measures of `runs`, and the cross-layer table they include (with its lines)."""
    x = cross_layer(runs, cn8)
    return {**measures(runs), **gate_measures(runs), **override_measures(runs, cn8, override_min),
            "expected_sent": expected_sent_share(runs), "own_ruling": own_ruling(runs),
            "cn8_iteration": cn8_data["summary"].get("iteration"), "cn8_source": Path(cn8_path).name,
            "cross_layer": {key: x[key] for key in ("majority", "runs", "end_to_end_runs")}}, x


def on_rows(run: list[dict]) -> list[dict]:
    """Feature 008: a run's rows with the switch on: the HS-6 chosen in place of the top-1, with its route and gate."""
    return [{**r, "top1": r["on"]["chosen"], "hit": r["on"]["hit"], "route": r["on"]["route"], "gate": r["on"]["gate"]}
            for r in run]


def override_measures(runs: list[list[dict]], cn8: dict[str, dict], override_min: int = OVERRIDE_MIN) -> dict:
    """Feature 008: the switch on, from the same rows (their `on` fields computed at `override_min`): the HS-6 measures
    and the end-to-end estimate on the HS-6 chosen, the overrides that fired, and the lines whose rulings supported the
    model's candidate 2 or 3 with how often it was right."""
    on = [on_rows(run) for run in runs]
    m, x = measures(on), cross_layer(on, cn8)
    return {"override_min": override_min,
            "on": {"top1_runs": m["top1_runs"], "majority_top1": m["majority_top1"], "routes_runs": m["routes_runs"],
                   "wrong_auto_runs": m["wrong_auto_runs"],
                   "right_auto_runs": [sum(r["hit"] and r["route"] == "auto_accept" for r in run) for run in on],
                   "cross_layer": {key: x[key] for key in ("majority", "runs", "end_to_end_runs")}},
            "overrides_runs": [[{"reference": r["reference"], "expected": r["expected"], "top1": r["top1"],
                                 "chosen": r["on"]["chosen"], "rank": r["on"]["rank"], "hit": r["on"]["hit"]}
                                for r in run if r["on"]["gate"] == "vote_override"] for run in runs],
            "supported_runs": [{"lines": sum(r["supported"]["rank"] is not None for r in run),
                                "right": sum(r["supported"]["right"] is True for r in run)} for run in runs]}


def set_files(name: str) -> tuple[Path, Path, Path]:
    """Feature 014a: a set's results, history and report files; the coolant and the outside set keep their own."""
    return {"coolant": (COOLANT_OUT, COOLANT_HISTORY, COOLANT_REPORT),
            "outside": (OUTSIDE_OUT, OUTSIDE_HISTORY, OUTSIDE_REPORT)}.get(name, (OUT, HISTORY, REPORT))


def set_file(name: str) -> Path:
    """Feature 014a: the file of a set of typed lines."""
    return OUTSIDE_SET if name == "outside" else COOLANT_SET


def write_results(report: dict, out: Path, name: str) -> Path:
    """Write the line-by-line results to `out`, the latest run's file, and to the run's own file next to it
    (hs6_eval.json → hs6_eval_<name>.json), which a later run with another name does not overwrite. Returns the latter."""
    text = dump_results(report)
    own = out.with_name(f"{out.stem}_{name}{out.suffix}")
    for path in (out, own):
        path.write_text(text, encoding="utf-8", newline="\n")
    return own


def cn8_results(data: dict) -> dict[str, dict]:
    """Per line of a CN-8 eval results file: its expected CN-8, and the chosen CN-8 and the top-1 hit of each run."""
    out: dict[str, dict] = {}
    for run in data.get("runs") or [data["rows"]]:
        for row in run:
            line = out.setdefault(row["reference"], {"expected": row["expected"], "chosen": [], "hits": []})
            line["chosen"].append(row["chosen"])
            line["hits"].append(bool(row["hit"]))
    return out


def _quadrant(hs6_right: bool, cn8_right: bool) -> str:
    return f"hs6_{'right' if hs6_right else 'wrong'}_cn8_{'right' if cn8_right else 'wrong'}"


def cross_layer(runs: list[list[dict]], cn8: dict[str, dict]) -> dict:
    """Each line's HS-6 (this eval) right or wrong × its CN-8 (the CN-8 eval, from the correct HS-6) right or wrong: on
    the majority top-1 of each eval (a tie goes to the earliest run), and run by run (run k of both). Both right is the
    end-to-end estimate, as the CN-8 step runs on the HS-6 picked, which is the correct one only when the HS-6 is right."""
    k = min(len(runs), min(len(c["hits"]) for c in cn8.values()))
    by_majority, per_run = dict.fromkeys(QUADRANTS, 0), [dict.fromkeys(QUADRANTS, 0) for _ in range(k)]
    lines = []
    for seen in zip(*runs):
        c = cn8[seen[0]["reference"]]
        hs6_right = majority([r["top1"] for r in seen]) == seen[0]["expected"]
        cn8_right = majority(c["chosen"]) == c["expected"]
        quadrant = _quadrant(hs6_right, cn8_right)
        by_majority[quadrant] += 1
        lines.append({"reference": seen[0]["reference"], "quadrant": quadrant, "hs6_hits": [r["hit"] for r in seen],
                      "cn8_hits": c["hits"]})
        for i, cells in enumerate(per_run):
            cells[_quadrant(seen[i]["hit"], c["hits"][i])] += 1
    return {"majority": by_majority, "runs": per_run, "end_to_end_runs": [cells["hs6_right_cn8_right"] for cells in per_run],
            "lines": lines}


# --------------------------------------------------------------------------- the report
def _md(text: str, limit: int = 80) -> str:
    """A description excerpt for a Markdown list: one line, cut, markup characters escaped."""
    text = " ".join((text or "").split())
    text = text if len(text) <= limit else text[:limit - 1] + "…"
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)


def _runs(values: list) -> str:
    return " / ".join(str(v) for v in values)


def _seen_text(line: dict) -> str:
    return " · ".join(f"{s['top1'] or 'no code'} ({s['confidence']}, {s['route']})" for s in line["seen"])


def _wrong_auto(wrong_auto_runs: list[list[dict]]) -> list[str]:
    """The wrong but auto-accepted lines: those of every run as a count, as each is among the lines wrong in every run,
    and the others one by one with the runs they were in."""
    by_run = [{w["reference"]: w for w in wrong} for wrong in wrong_auto_runs]
    refs = list(dict.fromkeys(ref for found in by_run for ref in found))
    every = [ref for ref in refs if all(ref in found for found in by_run)]
    listed = []
    for ref in refs:
        if ref not in every:
            seen = [(k, found[ref]) for k, found in enumerate(by_run, start=1) if ref in found]
            listed.append(f"- {ref} (expected {seen[0][1]['expected']}): "
                          + "; ".join(f"run {k}: {w['top1']} ({w['confidence']})" for k, w in seen))
    return ([f"Per run: {_runs(len(found) for found in by_run)}. In every run: {len(every)} line{'' if len(every) == 1 else 's'}, "
             "each among the lines wrong in every run above."] + ([""] + listed if listed else []))


def _entry_sections(h: dict, descriptions: dict[str, str]) -> list[str]:
    n, x = h["n"], h["cross_layer"]
    run = f", {h['lang']}, query expansion {h['expansion']}" if "lang" in h else ""   # feature 009
    run += f", customs wording {h['customs_wording']}" if "customs_wording" in h else ""   # feature 014a
    out = ["", f"## Iteration {h['iteration']} ({h.get('tag', '-')}, {h['model']}{run}, {h['run_on']})"]
    if h.get("replay_of"):
        r, floor = h["replay_of"], h.get("replay")   # feature 014a: a replay at another similarity floor
        at = f"floor {floor['floor']} and OVERRIDE_MIN {h['override_min']}" if floor else f"OVERRIDE_MIN {h['override_min']}"
        out += ["", f"Replay of iteration {r['iteration']} ({r.get('tag') or '-'}) at {at}, from its stored answers: no "
                    "model call." + ("" if not floor or floor.get("exact", True)
                                     else f" Not exact ({floor.get('why', 'below the run' + chr(39) + 's floor')}), so no "
                                          "evidence for a new floor.")]
    if h.get("note"):
        out += ["", f"Note: {h['note']}"]
    if h.get("parse"):
        p = h["parse"]
        out += ["", f"Invalid answers (retried at most {p['retry_limit']} time{'' if p['retry_limit'] == 1 else 's'}): "
                + "; ".join(f"run {k + 1}: {r['retries']} retried ({r['unparseable']} not valid JSON, {r['schema_invalid']} "
                            f"not the schema), {r['failed_calls']} calls still invalid, {r['failed_lines']} lines failed"
                            for k, r in enumerate(p["runs"])) + "."]
    if h.get("confidence"):
        out += ["", "The model's own confidence of its top-1 (before the vague cap), all runs, right / wrong: "
                + " · ".join(f"{value}: {c['right']} / {c['wrong']}" for value, c in h["confidence"].items()) + "."]
    out += ["", "| Run | Top-1 | In top 3 | Auto-accept | Review | Ask the shipper | Wrong, auto-accepted |",
            "|---|---|---|---|---|---|---|"]
    for k, routes in enumerate(h["routes_runs"]):
        out.append(f"| {k + 1} | {h['top1_runs'][k]}/{n} | {h['top3_runs'][k]}/{n} | {routes['auto_accept']} | "
                   f"{routes['review']} | {routes['ask_shipper']} | {len(h['wrong_auto_runs'][k])} |")
    if "gate_runs" in h:
        out += _gate_table(h)
    m = x["majority"]
    out += ["", f"### Cross-layer: HS-6 (this eval) × CN-8 (CN-8 eval iteration {h['cn8_iteration']})", "",
            "The CN-8 eval starts from the correct HS-6, so a line is right end to end only when both are right. "
            "Majority: the majority top-1 of each eval; run k: run k of both.", "",
            "| | HS-6 right, CN-8 right (end to end) | HS-6 right, CN-8 wrong | HS-6 wrong, CN-8 right | "
            "HS-6 wrong, CN-8 wrong |", "|---|---|---|---|---|",
            "| Majority | " + " | ".join(str(m[q]) for q in QUADRANTS) + " |"]
    out += [f"| Run {k + 1} | " + " | ".join(str(cells[q]) for q in QUADRANTS) + " |" for k, cells in enumerate(x["runs"])]
    step1 = m["hs6_wrong_cn8_right"] + m["hs6_wrong_cn8_wrong"]
    out += ["", f"On majority results {n - m['hs6_right_cn8_right']} of {n} lines end wrong: {step1} from the HS-6 step "
                f"(the CN-8 step would have failed too on {m['hs6_wrong_cn8_wrong']} of them), "
                f"{m['hs6_right_cn8_wrong']} from the CN-8 step alone. End-to-end estimate per run: "
                f"{_runs(x['end_to_end_runs'])} of {n}."]
    s = h["expected_sent"]
    if s["wrong"]:
        out += ["", f"Wrong top-1 results (line × run): {s['wrong']}; the correct HS-6 was among the candidates shown to "
                    f"the model in {s['with_expected']} ({s['share']:.1%})."]
    o = h["own_ruling"]
    out += ["", f"Leakage guard: each line's own ruling was its nearest ruling in {_runs(o['nearest_runs'])} of {n} "
                f"lines (per run), among the {o['searched']} the precedent search reads in {_runs(o['searched_runs'])}; "
                "the guard kept it out of the precedents."]
    wrong = [f"- {a['reference']} (chapter {a['chapter']}, expected {a['expected']}): {_seen_text(a)}; correct in the top 3 "
             f"in {sum(s['in_top3'] for s in a['seen'])} of {len(a['seen'])} runs. \"{_md(descriptions.get(a['reference'], ''))}\""
             for a in h["always_wrong"]]
    differed = [f"- {u['reference']} (expected {u['expected']}): {_seen_text(u)}" for u in h["unstable"]]
    out += ["", f"### Lines wrong in every run ({len(wrong)})"] + ([""] + wrong if wrong else [])
    out += ["", f"### Lines whose top-1 differed between runs ({len(differed)})"] + ([""] + differed if differed else [])
    out += ["", "### Wrong but auto-accepted (the HS-6 layer)", ""] + _wrong_auto(h["wrong_auto_runs"])
    if "on" in h:
        out += _override_section(h)
    return out


def _gate_table(h: dict) -> list[str]:
    """The vote gate's reasons per run (an entry from before rule (a) has no veto: 0)."""
    out = ["", "### Vote gate", "",
           "Gate reasons per run; not gated: a flagged or failed line, or one without a candidate. Vetoed: the gate passed, "
           "but the vote of the candidates' chapters sent the line to review (rule (a), feature 014a). Lost: right top-1 "
           "results the confidence rule alone would have auto-accepted and the gate did not.", "",
           "| Run | Vote agrees | Vote disagrees | Tie | Share low | Vetoed | No ruling | Not gated | No ruling, to review | "
           "Right auto-accepts | Lost |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    return out + [f"| {k + 1} | " + " | ".join(str(gates.get(g, 0)) for g in GATES)
                  + f" | {h['no_rulings_review_runs'][k]} | {h['right_auto_runs'][k]} | {h['lost_runs'][k]} |"
                  for k, gates in enumerate(h["gate_runs"])]


def _latest_run(history: list[dict]) -> str:
    """Which run the results file of the latest run holds: the last paid run of the history (a replay writes its own)."""
    runs = [h for h in history if not h.get("replay_of")]
    return f", iteration {runs[-1]['iteration']} ({runs[-1].get('tag', '-')})" if runs else ""


def _override_section(h: dict) -> list[str]:
    """Feature 008: the switch off (the entry above) against on, replayed from the same answers."""
    n, o = h["n"], h["on"]
    off_e2e, on_e2e = h["cross_layer"]["end_to_end_runs"], o["cross_layer"]["end_to_end_runs"]
    out = ["", "### Precedent override (feature 008)", "",
           f"With the switch on, at least {h['override_min']} of the nearest rulings at the model's candidate 2 or 3 choose "
           "that candidate and auto-accept it. The entry above is the switch off; the switch on is replayed from the same "
           "model answers and rulings, so the two differ only where an override fired. HS-6 right: the HS-6 chosen, the "
           "top-1 when no override fired.", "",
           "| Run | Switch | HS-6 right | Auto-accepted | Wrong, auto-accepted | Right auto-accepts | End to end (estimate) |",
           "|---|---|---|---|---|---|---|"]
    for k in range(len(h["top1_runs"])):
        for switch, m, e2e in (("off", h, off_e2e), ("on", o, on_e2e)):
            out.append(f"| {k + 1} | {switch} | {m['top1_runs'][k]}/{n} | {m['routes_runs'][k]['auto_accept']} | "
                       f"{len(m['wrong_auto_runs'][k])} | {m['right_auto_runs'][k]} | "
                       f"{f'{e2e[k]}/{n}' if k < len(e2e) else '-'} |")
    fired = h["overrides_runs"]
    out += ["", f"Overrides that fired per run: {_runs(len(f) for f in fired)}, of which chose the right HS-6: "
                f"{_runs(sum(x['hit'] for x in f) for f in fired)}. The rulings' majority supported the model's candidate 2 "
                f"or 3 on {_runs(s['lines'] for s in h['supported_runs'])} lines per run; that candidate was the right HS-6 "
                f"on {_runs(s['right'] for s in h['supported_runs'])}."]
    listed = [f"- run {k}: {x['reference']} (expected {x['expected']}): candidate {x['rank']}, {x['chosen']}, instead of "
              f"{x['top1']}; {'right' if x['hit'] else 'wrong'}" for k, f in enumerate(fired, start=1) for x in f]
    return out + ([""] + listed if listed else [])


def render_report(history: list[dict], data: dict) -> str:
    descriptions = {r["reference"]: r["description"] for r in data["rulings"]}
    out = [
        "# HS-6 evaluation report (feature 006)",
        "",
        f"- **Set**: `tests/eval/cn8_eval_set.json`, the CN-8 eval's {len(data['rulings'])} EBTI rulings (built "
        f"{data['built_on']}); a line's correct HS-6 is the first six digits of its ruling's CN-8.",
        "- **Method**: each ruling's goods description, as given, is a new line through the app's path: the description "
        "check, the HS-6 step (hybrid search and BTI precedents, no shipper history) and the route the store computes "
        f"(threshold {DEFAULT_THRESHOLD}; a vague line goes to ask the shipper, before the vague rule of 2026-11-19 only "
        f"below the ask floor of {ASK_FLOOR}). A line's own ruling is never a precedent (leave-one-out); "
        "ruling validity on the set's build date. `python tests/eval/hs6_eval.py --repeat 3`.",
        "- **Top-1** is the first candidate; a line without one (a stop word, a failure) is a miss. **In top 3**: the "
        "correct HS-6 among the candidates the clerk picks from on review. **Majority**: the most frequent top-1 over the "
        "runs (a tie goes to the earliest run). **Wrong, auto-accepted**: routed to auto-accept with a wrong top-1; the "
        "CN-8 step then runs on the wrong HS-6.",
        f"- **Vote gate** (the entries with gate reasons): the {HS6_VOTE_K} nearest eligible rulings at or above a cosine "
        f"similarity of {HS6_VOTE_MIN_SIMILARITY} vote on the first six digits, and the model's top-1 is auto-accepted "
        f"when it is their majority with a share of at least {HS6_VOTE_SHARE}; the threshold applies only when none votes. "
        "**Lost**: right top-1 results the confidence rule alone would have auto-accepted and the gate did not.",
        "",
        "| Iteration | Run on | Tag | Runs | Top-1 per run | Majority top-1 | In top 3 per run | Same top-1 | Same route | "
        "Wrong, auto-accepted per run | End to end per run | Auto-accepted per run | Right auto-accepts lost per run | "
        "Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for h in history:
        n = h["n"]
        out.append(f"| {h['iteration']} | {h['run_on']} | {h.get('tag', '-')} | {h['repeat']} | {_runs(h['top1_runs'])} "
                   f"of {n} | {h['majority_top1']}/{n} | {_runs(h['top3_runs'])} of {n} | {h['same_top1']}/{n} | "
                   f"{h['same_route']}/{n} | {_runs(len(w) for w in h['wrong_auto_runs'])} | "
                   f"{_runs(h['cross_layer']['end_to_end_runs'])} of {n} | "
                   f"{_runs(routes['auto_accept'] for routes in h['routes_runs'])} | "
                   f"{_runs(h['lost_runs']) if 'lost_runs' in h else '-'} | ${h['cost_usd']:.4f} (€{h['cost_eur']:.4f}), "
                   f"{h['elapsed_s']:.0f} s |")
    for h in history:
        out += _entry_sections(h, descriptions)
    out += ["", f"Model: {history[-1]['model'] if history else '-'}. Line-by-line results of the latest run"
            f"{_latest_run(history)}: `tests/eval/hs6_eval.json`; since feature 007 each run also keeps its own, "
            "`tests/eval/hs6_eval_<tag>.json`; earlier runs are in the git history of `hs6_eval.json`.", ""]
    return "\n".join(out)


def render_coolant_report(history: list[dict], data: dict, set_name: str = "coolant") -> str:
    """Feature 014a: tests/eval/hs6_eval_coolant.md, one row per entry and, per entry, each line's outcome per run and on
    majority; the outside set's hs6_eval_outside.md the same way (`set_name`)."""
    texts = {line["id"]: line["text"] for line in data["lines"]}
    guard = ("each line's source ruling is kept out (leave-one-out), its id being that ruling's reference"
             if set_name == "outside" else "no leakage guard, as no line is a ruling")
    out = [
        f"# HS-6 evaluation report: the {set_name} set (feature 014a)",
        "",
        f"- **Set**: `tests/eval/{set_file(set_name).name}`, {len(data['lines'])} lines (built {data['built_on']}): "
        f"{data['source']}.",
        "- **Method**: each line, as typed, goes through the 120-line set's path: the description check, the HS-6 step "
        "(hybrid search and BTI precedents, no shipper history) and the route the store computes (threshold "
        f"{DEFAULT_THRESHOLD}; a vague line goes to ask the shipper, before the vague rule of 2026-11-19 only below the "
        f"ask floor of {ASK_FLOOR}); {guard}; ruling validity on the set's build date. "
        f"`python tests/eval/hs6_eval.py --set {set_name} --repeat 3`.",
        "- **Right**: a line with an expected HS-6 when its top-1 is that code; a line expecting \"ask the shipper\" when "
        "its route is ask_shipper, whatever codes it shows. **Majority**: a line's most frequent top-1, or route for a "
        "line expecting \"ask the shipper\" (a tie goes to the earliest run). **In top 3**: the lines with an expected "
        "HS-6 only. **Wrong, auto-accepted**: auto-accepted and not right. **No ruling voted**: the vote gate's "
        "no_rulings lines. **Vetoed**: the lines the vote of the candidates' chapters sent to review (rule (a)).",
        "",
        "| Iteration | Run on | Tag | Runs | Query expansion | Customs wording | Floor | Right per run | Majority right | "
        "In top 3 per run | Auto-accepted per run | Wrong, auto-accepted per run | No ruling voted per run | "
        "Vetoed per run | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for h in history:
        n = h["n"]
        out.append(f"| {h['iteration']} | {h['run_on']} | {h.get('tag', '-')} | {h['repeat']} | {h.get('expansion', '-')} | "
                   f"{h.get('customs_wording', '-')} | {h.get('floor', '-')} | "
                   f"{_runs(h['top1_runs'])} of {n} | {h['majority_top1']}/{n} | {_runs(h['top3_runs'])} | "
                   f"{_runs(routes['auto_accept'] for routes in h['routes_runs'])} | "
                   f"{_runs(len(w) for w in h['wrong_auto_runs'])} | {_runs(g['no_rulings'] for g in h['gate_runs'])} | "
                   f"{_runs(g.get('scoped_veto', 0) for g in h['gate_runs'])} | "
                   f"${h['cost_usd']:.4f} (€{h['cost_eur']:.4f}), {h['elapsed_s']:.0f} s |")
    for h in history:
        k = len(h["top1_runs"])
        out += ["", f"## Iteration {h['iteration']} ({h.get('tag', '-')}, {h['model']}, query expansion "
                    f"{h.get('expansion', '-')}, customs wording {h.get('customs_wording', '-')}, {h['run_on']})"]
        if h.get("replay"):
            r = h["replay"]
            out += ["", f"Replay of iteration {h['replay_of']['iteration']} ({h['replay_of'].get('tag') or '-'}) at floor "
                        f"{r['floor']}, from its vote_hits: no model call"
                        + ("." if r.get("exact", True) else f"; not exact ({r.get('why', 'below the run' + chr(39) + 's floor')}), "
                                                             "so no evidence.")]
        if h.get("note"):
            out += ["", f"Note: {h['note']}"]
        out += ["", "| Line | Text | Expected | " + " | ".join(f"Run {i + 1}" for i in range(k)) + " | Majority | Right |",
                "|---|---|---|" + "---|" * k + "---|---|"]
        for line in h["lines"]:
            seen = " | ".join(f"{s['top1'] or 'no code'} ({s['route']})" for s in line["seen"])
            out.append(f"| {line['id']} | {_md(texts.get(line['id'], ''), 60)} | {line['expected']} | {seen} | "
                       f"{line['majority'] or 'no code'} | {'yes' if line['right'] else 'no'} |")
    out += ["", f"Model: {history[-1]['model'] if history else '-'}. Line-by-line results of the latest run"
            f"{_latest_run(history)}: `tests/eval/hs6_eval_{set_name}.json`; each run also keeps its own, "
            f"`tests/eval/hs6_eval_{set_name}_<tag>_….json`.", ""]
    return "\n".join(out)


def replay_main(args: argparse.Namespace, data: dict, cn8: dict[str, dict], cn8_data: dict, override_min: int) -> int:
    """Feature 008: a stored run's answers with the switch on at `override_min`, with no model call. The replay keeps its
    own results file (hs6_eval.json stays the latest paid run), a history entry marked as a replay, and the report."""
    source = json.loads(Path(args.replay).read_text(encoding="utf-8"))
    s = source["summary"]
    runs = replay_runs(source, override_min)
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    iteration = max((h["iteration"] for h in history), default=0) + 1
    m, x = entry_measures(runs, cn8, cn8_data, args.cn8, override_min)
    entry = {"iteration": iteration, "run_on": date.today().isoformat(),
             "change": f"replay of iteration {s['iteration']} at OVERRIDE_MIN {override_min}; no model call",
             **({"tag": args.tag} if args.tag else {}), "set": "cn8",
             **{k: s[k] for k in ("model", "reasoning", "lang", "expansion", "threshold", "ask_floor", "temperature",
                                  "seed", "repeat", "n") if k in s},
             "replay_of": {"iteration": s["iteration"], "tag": s.get("tag")}, **m,
             **({"parse": s["parse"]} if "parse" in s else {}), "confidence": confidence_table(runs),
             "elapsed_s": 0.0, "cost_usd": 0.0, "cost_eur": 0.0, "cost_eur_runs": [0.0] * len(runs)}
    if args.note:
        entry["note"] = args.note
    report: dict = {"summary": {**entry, "set_built_on": data["built_on"], "cn8_lines": x["lines"]}, "rows": runs[0]}
    if len(runs) > 1:
        report["runs"] = runs
    history = sorted([h for h in history if h["iteration"] != iteration] + [entry], key=lambda h: h["iteration"])
    if args.dry_run:
        print("\n== tests/eval/hs6_eval.md:\n" + render_report(history, data))
        print("dry run: nothing written")
    else:
        own = OUT.with_name(f"{OUT.stem}_{args.tag or f'iteration{iteration}'}{OUT.suffix}")
        own.write_text(dump_results(report), encoding="utf-8", newline="\n")
        HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        REPORT.write_text(render_report(history, data), encoding="utf-8", newline="\n")
    on, fired, n = entry["on"], entry["overrides_runs"], entry.get("n", len(runs[0]))
    print(f"HS-6 replay of iteration {s['iteration']} at OVERRIDE_MIN {override_min}, no model call")
    print(f"  switch off: top-1 per run {m['top1_runs']} of {n}; auto-accepted {[r['auto_accept'] for r in m['routes_runs']]}; "
          f"wrong but auto-accepted {[len(w) for w in m['wrong_auto_runs']]}; end to end {x['end_to_end_runs']}")
    print(f"  switch on:  top-1 per run {on['top1_runs']} of {n}; auto-accepted "
          f"{[r['auto_accept'] for r in on['routes_runs']]}; wrong but auto-accepted {[len(w) for w in on['wrong_auto_runs']]}; "
          f"end to end {on['cross_layer']['end_to_end_runs']}; overrides {[len(f) for f in fired]}, right "
          f"{[sum(o['hit'] for o in f) for f in fired]}")
    return 0


def replay_floor_main(ap: argparse.ArgumentParser, args: argparse.Namespace, override_min: int) -> int:
    """Feature 014a: a stored run's votes rebuilt at the similarity floor --floor from each row's vote_hits, with the
    routing functions and no model call (floor_fields); exact, and evidence for a new floor, only at or above the run's
    own floor. The replay belongs to the set its file names: it keeps its own results file and an entry in that set's
    history and report; a coolant replay reads no CN-8 results."""
    source = json.loads(Path(args.replay).read_text(encoding="utf-8"))
    s = source["summary"]
    set_name = s.get("set", "cn8")
    stored = source.get("runs") or [source["rows"]]
    if not all("vote_hits" in r for run in stored for r in run):
        ap.error(f"{args.replay} keeps no vote_hits: only a run made since feature 014a replays at another floor")
    runs = [[floor_fields(r, args.floor, override_min) for r in run] for run in stored]
    if set_name in TYPED_SETS:
        data = json.loads(set_file(set_name).read_text(encoding="utf-8"))
        m, x = typed_measures(runs, override_min), None
    else:
        data = json.loads(SET.read_text(encoding="utf-8"))
        cn8_data = json.loads(Path(args.cn8).read_text(encoding="utf-8"))
        cn8 = cn8_results(cn8_data)
        missing = [r["reference"] for r in runs[0] if r["reference"] not in cn8]
        if missing:
            ap.error(f"{len(missing)} lines are missing from {args.cn8}, such as {missing[0]}")
        m, x = entry_measures(runs, cn8, cn8_data, args.cn8, override_min)
    out, history_file, report_file = set_files(set_name)
    history = json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else []
    iteration = max((h["iteration"] for h in history), default=0) + 1
    why = "; ".join(reason for reason, holds in (
        ("below the run's floor", args.floor < s.get("floor", HS6_VOTE_MIN_SIMILARITY)),
        ("several query vectors: query expansion or customs wording was on, and the gate's vote is rebuilt from one "
         "merged list of nearest rulings", s.get("expansion") == "on" or s.get("customs_wording") == "on")) if holds)
    exact = not why
    entry = {"iteration": iteration, "run_on": date.today().isoformat(),
             "change": (f"replay of iteration {s['iteration']} at floor {args.floor}"
                        + ("" if exact else f", not exact: {why}") + "; no model call"),
             **({"tag": args.tag} if args.tag else {}), "set": set_name,
             **{k: s[k] for k in ("model", "reasoning", "lang", "expansion", "customs_wording", "threshold", "ask_floor",
                                  "temperature", "seed", "repeat", "n") if k in s},
             "floor": args.floor, "replay_of": {"iteration": s["iteration"], "tag": s.get("tag")},
             "replay": {"of": Path(args.replay).name, "floor": args.floor, "exact": exact, **({} if exact else {"why": why})},
             **m,
             "elapsed_s": 0.0, "cost_usd": 0.0, "cost_eur": 0.0, "cost_eur_runs": [0.0] * len(runs)}
    if args.note:
        entry["note"] = args.note
    report: dict = {"summary": {**entry, "set_built_on": data["built_on"], **({} if x is None else {"cn8_lines": x["lines"]})},
                    "rows": runs[0]}
    if len(runs) > 1:
        report["runs"] = runs
    history = sorted([h for h in history if h["iteration"] != iteration] + [entry], key=lambda h: h["iteration"])
    render = (lambda h, d: render_coolant_report(h, d, set_name)) if set_name in TYPED_SETS else render_report
    if args.dry_run:
        print(f"\n== tests/eval/{report_file.name}:\n" + render(history, data))
        print("dry run: nothing written")
    else:
        own = out.with_name(f"{out.stem}_{args.tag or f'iteration{iteration}'}{out.suffix}")
        own.write_text(dump_results(report), encoding="utf-8", newline="\n")
        history_file.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        report_file.write_text(render(history, data), encoding="utf-8", newline="\n")
    print(f"HS-6 replay of iteration {s['iteration']} ({set_name}) at floor {args.floor}"
          f"{'' if exact else f' (not exact: {why})'}, OVERRIDE_MIN {override_min}, no model call")
    print(f"  per run: routes {m['routes_runs']}; wrong but auto-accepted {[len(w) for w in m['wrong_auto_runs']]}; no ruling "
          f"voted {m['no_voter_runs']}; right auto-accepts {m['right_auto_runs']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # German and Chinese text; a redirected Windows console is cp1252
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--iteration", type=int, help="iteration number (default: the next)")
    ap.add_argument("--change", help="what changed since the previous iteration (generated when omitted)")
    ap.add_argument("--repeat", type=int, default=1, help="run every line N times, independently (default 1)")
    ap.add_argument("--temperature", type=float, help="chat-model temperature for this run only")
    ap.add_argument("--seed", type=int, help="chat-model seed for this run only")
    ap.add_argument("--model", help="OpenRouter chat model for this run only (default: the configured one)")
    ap.add_argument("--tag", help="tag of the history entry")
    ap.add_argument("--note", help="a note kept with the history entry and shown with it in the report")
    ap.add_argument("--cn8", default=str(CN8_RESULTS), help="the CN-8 eval results the cross-layer table reads")
    ap.add_argument("--limit", type=int, help="only the first N lines of the set (with --dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="print a row, the history entry and the report; write nothing")
    ap.add_argument("--replay", help="feature 008: a results file whose stored answers are replayed at --override-min, "
                                     "with no model call")
    ap.add_argument("--override-min", type=int, help=f"the OVERRIDE_MIN of a --replay (default {OVERRIDE_MIN})")
    ap.add_argument("--lang", choices=("en", "zh"), default="en",
                    help="feature 009: en, the 120 lines as given (default); zh, the 30 lines of hs6_eval_zh.json in Chinese")
    ap.add_argument("--expansion", choices=("on", "off"),
                    help="feature 009: query expansion for this run (default: CARGOLINT_QUERY_EXPANSION)")
    ap.add_argument("--set", choices=("cn8", *TYPED_SETS), default="cn8", dest="set_name",
                    help="feature 014a: cn8, the 120 rulings of cn8_eval_set.json (default); coolant, the nine lines of "
                         "hs6_eval_coolant_set.json; outside, the lines of hs6_eval_outside_set.json, each line's source "
                         "ruling kept out")
    ap.add_argument("--customs-wording", choices=("on", "off"),
                    help="feature 014a: the customs-wording switch for this run (default: CARGOLINT_CUSTOMS_WORDING)")
    ap.add_argument("--floor", type=float, help="feature 014a: the similarity floor a --replay rebuilds the votes at, from "
                                                "the rows' nearest_hits and vote_hits (exact at or above the run's floor, "
                                                "for a run with query expansion and customs wording off)")
    ap.add_argument("--vote-scope", choices=("candidates", "all"), default="candidates",
                    help="the 014a regression ablation, eval only: the second HS-6 vote's ruling search within the "
                         "candidates' chapters (the app's, default) or over every chapter (then it equals the gate's vote "
                         "and never vetoes)")
    ap.add_argument("--proposal-scope", choices=("all", "nomenclature"), default="all",
                    help="option (c) of the author's decision of 2026-11-19, eval only: the candidate proposal's ruling "
                         "search over every chapter (the app's, default) or within the chapters of the nomenclature "
                         "search's subheadings; the gate's vote reads every chapter either way")
    ap.add_argument("--family-exclusion", action="store_true",
                    help="backlog item 21, eval only: a family member's exclusion also keeps its siblings' rulings out "
                         "(from tests/eval/hs6_eval_families.json); the default keeps only the line's own ruling out")
    args = ap.parse_args(argv)
    if args.replay and args.vote_scope != "candidates":
        ap.error("--vote-scope is for a run: a replay searches no rulings")
    if args.replay and args.proposal_scope != "all":
        ap.error("--proposal-scope is for a run: a replay searches no rulings")
    coolant = args.set_name in TYPED_SETS   # a set of typed lines: the coolant set's scoring, files and report
    if args.family_exclusion and coolant:
        ap.error("--family-exclusion is for the 120-line set: the coolant and outside sets have no families")
    if args.family_exclusion and args.replay:
        ap.error("--family-exclusion is for a run: a replay searches no rulings")
    if args.floor is not None and not args.replay:
        ap.error("--floor is for a --replay: a run uses HS6_VOTE_MIN_SIMILARITY")
    if args.floor is not None and not 0.0 <= args.floor <= 1.0:
        ap.error("--floor is a cosine similarity between 0 and 1")
    if args.repeat < 1:
        ap.error("--repeat must be 1 or more")
    if args.limit is not None and not args.dry_run:
        ap.error("--limit is for a dry run: the history keeps whole-set runs only")
    if args.tag is not None and not TAG_RE.fullmatch(args.tag):
        ap.error("--tag names the run's results file: letters, digits, '.', '_' and '-'")
    if args.override_min is not None and not args.replay:
        ap.error("--override-min is for a --replay: a run computes the switch on at OVERRIDE_MIN")
    if args.replay and not 1 <= (args.override_min or OVERRIDE_MIN) <= HS6_VOTE_K:
        ap.error(f"--override-min must be between 1 and {HS6_VOTE_K}")
    if args.replay and args.floor is not None:         # feature 014a: the set comes from the file
        return replay_floor_main(ap, args, args.override_min or OVERRIDE_MIN)
    if args.replay and json.loads(Path(args.replay).read_text(encoding="utf-8"))["summary"].get("set") in TYPED_SETS:
        ap.error("a coolant or outside run replays at another floor only: give --floor")
    if coolant and args.lang != "en":
        ap.error(f"--lang is for the 120-line set: the {args.set_name} set's lines are run as typed")
    if coolant and args.replay:
        ap.error("--replay replays the 120-line set's results")
    if coolant:
        data = json.loads(set_file(args.set_name).read_text(encoding="utf-8"))
        rulings = coolant_items(data)
        cn8 = cn8_data = None
    else:
        data = json.loads(SET.read_text(encoding="utf-8"))
        rulings = eval_rulings(data, args.lang)
    rulings = rulings[:args.limit] if args.limit else rulings
    if not coolant:
        cn8_data = json.loads(Path(args.cn8).read_text(encoding="utf-8"))
        cn8 = cn8_results(cn8_data)
        missing = [r["reference"] for r in rulings if r["reference"] not in cn8]
        if missing:
            ap.error(f"{len(missing)} lines are missing from {args.cn8}, such as {missing[0]}")
        if args.replay:
            return replay_main(args, data, cn8, cn8_data, args.override_min or OVERRIDE_MIN)
    family_members: dict[str, list[str]] = {}
    siblings: dict[str, frozenset[str]] = {}
    if not coolant:
        family_members = load_families()   # backlog item 21: the 120-line set's families
        siblings = family_siblings(family_members)
    out, history_file, report_file = set_files(args.set_name)
    as_of = date.fromisoformat(data["built_on"])
    settings, found = run_settings(get_settings(), args.model)
    reasoning = {"enabled": False} if settings.reasoning_off else None   # what the calls carry
    usage = Usage()
    kb = open_knowledge_base(settings, usage_sink=usage.add)
    overrides = {k: v for k, v in (("temperature", args.temperature), ("seed", args.seed)) if v is not None}
    if overrides:
        set_client_factory(lambda: OverriddenClient(settings, overrides))
    client = get_client(usage_sink=usage.add, settings=settings)
    price_for_run(client, found)
    if found is not None:
        client.max_retries = OTHER_MODEL_RETRIES
    invalid = count_invalid(client)
    model = client.raw._model
    temperature, seed = getattr(model, "temperature", None), getattr(model, "seed", None)   # what the calls carry
    history = json.loads(history_file.read_text(encoding="utf-8")) if history_file.exists() else []
    iteration = args.iteration if args.iteration is not None else max((h["iteration"] for h in history), default=0) + 1
    change = args.change or (f"{args.repeat} independent run{'s' if args.repeat > 1 else ''}, temperature {temperature}, "
                             f"seed {seed if seed is not None else 'none'}")
    expansion = settings.query_expansion if args.expansion is None else args.expansion == "on"
    wording = settings.customs_wording if args.customs_wording is None else args.customs_wording == "on"   # feature 014a
    print(f"HS-6 iteration {iteration}: {len(rulings)} lines ({f'the {args.set_name} set' if coolant else args.lang}, query "
          f"expansion {'on' if expansion else 'off'}, customs wording {'on' if wording else 'off'}) × {args.repeat} run(s); "
          f"BTI vectors "
          f"{'loaded' if getattr(kb, 'bti_vectors', None) is not None else 'not loaded'}; model {settings.chat_model}, "
          f"temperature {temperature}, seed {seed}"
          + ("" if coolant else f"; CN-8 results: iteration {cn8_data['summary'].get('iteration')}"))

    runs, elapsed, costs, parsed = [], 0.0, [], []
    for k in range(args.repeat):
        before = usage.cost_eur
        invalid.clear()
        rows, seconds = run_once(rulings, kb, client, as_of, settings.workers, expansion,
                                 leave_one_out=args.set_name != "coolant",
                                 customs_wording=wording, vote_scope=args.vote_scope, proposal_scope=args.proposal_scope,
                                 family_exclusion=args.family_exclusion, siblings=siblings)
        runs.append(rows)
        parsed.append(parse_counts(invalid, rows))
        elapsed += seconds
        costs.append(round(usage.cost_eur - before, 4))
        scored = f"right {sum(r['right'] for r in rows)}" if coolant else f"top-1 {sum(r['hit'] for r in rows)}"
        print(f"  run {k + 1}: {scored}/{len(rows)}, in top 3 {sum(r['in_top3'] for r in rows)}, "
              f"{seconds:.0f} s, €{costs[-1]:.4f}; invalid answers {parsed[-1]}")
    if coolant:   # feature 014a: no cross-layer table, as no line has a CN-8 result
        m, x = typed_measures(runs), None
    else:
        m, x = entry_measures(runs, cn8, cn8_data, args.cn8)
        m = {**m, "family": family_measures(runs, family_members)}   # backlog item 21: per-family metric
    entry = {
        "iteration": iteration, "run_on": date.today().isoformat(), "change": change,
        **({"tag": args.tag} if args.tag else {}), "set": args.set_name, "model": settings.chat_model,
        "reasoning": reasoning, **({} if coolant else {"lang": args.lang}), "expansion": "on" if expansion else "off",
        "customs_wording": "on" if wording else "off", "floor": HS6_VOTE_MIN_SIMILARITY,
        **({} if args.vote_scope == "candidates" else {"vote_scope": args.vote_scope}),
        **({} if args.proposal_scope == "all" else {"proposal_scope": args.proposal_scope}),
        **({} if not args.family_exclusion else {"family_exclusion": True}),
        "threshold": DEFAULT_THRESHOLD, "ask_floor": ASK_FLOOR, "temperature": temperature, "seed": seed,
        "repeat": args.repeat, "n": len(rulings), **m,
        "parse": {"retry_limit": client.max_retries, "runs": parsed},
        **({} if coolant else {"confidence": confidence_table(runs)}),
        "elapsed_s": round(elapsed, 1), "cost_usd": round(usage.cost_usd, 4), "cost_eur": round(usage.cost_eur, 4),
        "cost_eur_runs": costs}
    if args.note:
        entry["note"] = args.note
    summary = {**entry, "set_built_on": data["built_on"], **({} if x is None else {"cn8_lines": x["lines"]}),
               "usage": {"total_tokens": usage.total_tokens, "prompt_tokens": usage.prompt_tokens,
                         "completion_tokens": usage.completion_tokens, "calls": usage.calls,
                         "cost_usd": round(usage.cost_usd, 4), "cost_eur": round(usage.cost_eur, 4)}}
    report: dict = {"summary": summary, "rows": runs[0]}
    if args.repeat > 1:
        report["runs"] = runs
    history = [h for h in history if h["iteration"] != iteration] + [entry]
    history.sort(key=lambda h: h["iteration"])
    render = (lambda h, d: render_coolant_report(h, d, args.set_name)) if coolant else render_report
    n = len(rulings)
    if args.dry_run:
        first = runs[0][0]
        print("\n== a row (run 1, line 1; nearest_hits: the first 3 of "
              f"{len(first['nearest_hits'])}):\n" + json.dumps({**first, "nearest_hits": first["nearest_hits"][:3]},
                                                                ensure_ascii=False, indent=1))
        print(f"\n== the summary in tests/eval/{out.name} (the history entry plus "
              f"{'' if coolant else 'cn8_lines and '}usage):\n" + json.dumps(summary, ensure_ascii=False, indent=1))
        print(f"\n== tests/eval/{report_file.name}:\n" + render(history, data))
        print("dry run: nothing written")
    else:
        write_results(report, out, results_name(args.tag or f"iteration{iteration}", args.lang, expansion, wording))
        history_file.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        report_file.write_text(render(history, data), encoding="utf-8", newline="\n")
    if coolant:
        print(f"HS-6, {args.set_name} set: right per run {m['top1_runs']} of {n}; majority right {m['majority_top1']}/{n}; in top 3 "
              f"per run {m['top3_runs']}; auto-accepted per run {[routes['auto_accept'] for routes in m['routes_runs']]}; "
              f"wrong but auto-accepted per run {[len(w) for w in m['wrong_auto_runs']]}; no ruling voted per run "
              f"{[g['no_rulings'] for g in m['gate_runs']]}")
        for line in m["lines"]:
            print(f"  {line['id']}: expected {line['expected']}, majority {line['majority'] or 'no code'} "
                  f"({'right' if line['right'] else 'wrong'})")
        print(f"  model {settings.chat_model}, reasoning {reasoning}; invalid answers per run (retried at most "
              f"{client.max_retries} times) {parsed}")
        print(f"  {elapsed:.0f} s; usage {usage.total_tokens} tokens, {usage.calls} calls, ${usage.cost_usd:.4f} ≈ "
              f"€{usage.cost_eur:.4f}")
        return 0
    mx = x["majority"]
    print(f"HS-6 top-1 per run {m['top1_runs']} of {n}; majority {m['majority_top1']}/{n}; in top 3 per run {m['top3_runs']}; "
          f"same top-1 in all runs {m['same_top1']}/{n}; same route {m['same_route']}/{n}")
    print(f"  chapter per run {m['chapter_runs']}, majority {m['majority_chapter']}/{n}; heading per run {m['heading_runs']}, "
          f"majority {m['majority_heading']}/{n}; wrong by level {m['wrong_levels']}")
    print(f"  family metric {m['family']['family_majority']} of {m['family']['family_units']} units "
          f"({len(m['family']['per_family'])} families, {m['family']['standalone']} standalone right)")
    print(f"  auto-accepted per run {[routes['auto_accept'] for routes in m['routes_runs']]}; wrong but auto-accepted per "
          f"run {[len(w) for w in m['wrong_auto_runs']]}; wrong in every run {len(m['always_wrong'])}")
    print(f"  gate per run {entry['gate_runs']}; no ruling, to review {entry['no_rulings_review_runs']}; right "
          f"auto-accepts {entry['right_auto_runs']}; lost {entry['lost_runs']}")
    print(f"  cross-layer (majority) {mx}; end to end per run {x['end_to_end_runs']} of {n}")
    on, fired = entry["on"], entry["overrides_runs"]
    print(f"  switch on (OVERRIDE_MIN {entry['override_min']}): top-1 per run {on['top1_runs']}; auto-accepted per run "
          f"{[routes['auto_accept'] for routes in on['routes_runs']]}; wrong but auto-accepted per run "
          f"{[len(w) for w in on['wrong_auto_runs']]}; end to end per run {on['cross_layer']['end_to_end_runs']} of {n}; "
          f"overrides per run {[len(f) for f in fired]}, right {[sum(x['hit'] for x in f) for f in fired]}")
    print(f"  own ruling nearest per run {entry['own_ruling']['nearest_runs']}")
    print(f"  model {settings.chat_model}, reasoning {reasoning}; invalid answers per run (retried at most "
          f"{client.max_retries} times) {parsed}")
    print(f"  {elapsed:.0f} s; usage {usage.total_tokens} tokens, {usage.calls} calls, ${usage.cost_usd:.4f} ≈ €{usage.cost_eur:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
