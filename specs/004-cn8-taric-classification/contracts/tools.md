# Contract: tools, guardrail functions, line store and agent, changes for CN-8 and TARIC-10

Changes feature 001's [tools.md](../../001-packing-list-check/contracts/tools.md); everything not named here is
unchanged. Constitution v1.2.0 lists seven tools; this feature adds `classify_cn8` and `lookup_taric`.
- **`classify_cn8`**: justified because the CN-8 needs its own evidence, the CN-8 lines and EBTI rulings at eight digits, without touching the HS-6 path (FR-021).
- **`lookup_taric`**: justified because the TARIC step is a deterministic lookup with its own rules, which a clerk-facing agent must be able to call and report.

Field meanings are in [data-model.md](../data-model.md).

## 1. Tools

### 1.6 `classify_cn8` (new)

Purpose: the CN-8 under each decided HS-6, with confidence, evidence and EBTI precedent, or the attribute to ask the
shipper about (FR-001 to FR-006).

```text
Input  Cn8Input                       # function input; Pydantic, agent/schemas.py
  lines: [{line_no, text_zh, text_en, extracted|None, hs6}]      # only lines whose HS-6 is decided
  as_of: date
  threshold: int                      # the shipment's auto-accept threshold, applied in code
Agent-facing wrapper args: line_nos: [int]|None (omit → every line with a decided HS-6 and no CN-8 choice yet)
Output [Cn8Result]                    # one per input line; Pydantic, agent/schemas.py
  line_no
  choice: Cn8Choice                   # data-model §3; on failure it carries `error` and no CN-8,
                                      # and the line routes to review (data-model §6)
  status: checked|failed, error_reason
Structured model output Cn8Out        # validated before use; invalid → one retry, then the line fails this step
  cn8: "########"|null, confidence: 0-100, deciding_attribute: str, attribute_visible: bool,
  evidence: str, rationale: str, precedent: str|null           # a ruling reference sent in this call
```

Pipeline per line:
1. Read the CN-8 options under `hs6` (`NomenclatureIndex.cn8_lines`). With one option, write it by rule at confidence 100, with no model call.
2. Select up to 8 valid EBTI rulings under `hs6`, at most 2 per CN-8 line. They are the nearest to the line text when BTI vectors are loaded, else the newest.
3. Make one structured call. The line text and the ruling excerpts are fenced as data.
4. Validate in code:
   - `cn8` must be among the options;
   - a cited ruling must be among those sent;
   - `attribute_visible` false, or a null `cn8`, gives `question` and no CN-8.
5. Write by rule when `confidence` is at least `threshold`; otherwise the CN-8 is a suggestion.

### 1.7 `lookup_taric` (new)

Purpose: the TARIC subdivisions and measures for each line's CN-8 and the shipment's origin, with the rules applied
(FR-007 to FR-012). The only model call is the optional subdivision suggestion.

```text
Input  TaricInput                     # function input; Pydantic, agent/schemas.py
  lines: [{line_no, text_zh, text_en, cn8, cn8_written: bool}]
  origin: str                         # Shipment.taric_origin
Agent-facing wrapper args: line_nos: [int]|None (omit → every line with a CN-8 and no TARIC outcome for the current origin)
Output [TaricResult]                  # one per input line; Pydantic, agent/schemas.py
  line_no
  outcome: TaricOutcome               # data-model §4
  status: checked|failed, error_reason
Structured model output SubdivisionOut   # only for rule "choose"; validated; never written
  code: "##########"|null, confidence: 0-100, attribute_visible: bool, rationale: str
```

The steps:
1. **Lookup**: `kb.taric.lookup_taric(cn8, origin)` (feature 003, unchanged). With no snapshot loaded, the rule is `not_loaded`.
2. **Rule**: `taric_rule(subdivisions, snapshot_loaded)` chooses the rule, and `code_to_write(...)` decides what is written.
3. **Suggestion**: for `choose`, a suggestion is kept only when `attribute_visible` is true and `code` is among the subdivisions.
4. **Audit**: every outcome is recorded (data-model §5).

### 1.5 `apply_shipper_reply` (behaviour unchanged)

The reply's new version starts without a CN-8 choice or TARIC outcome. A version created by a reply is never
auto-accepted (feature 001's lock), so only the clerk's click decides its HS-6. That click runs the two steps for the
line (`after_hs6_decision`, §4); `apply_shipper_reply` makes no CN-8 or TARIC call itself (FR-006). It still touches
that line only (Principle V).

## 2. Pure guardrail functions (additions; `agent/routing.py`, `agent/taric_rules.py`)

```text
route_line(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor,
           cn8_question: str|None = None, cn8_error: str|None = None) -> (Route, reason)   # data-model §6
hs6_auto_decided(flag_kind, top_confidence, status, ever_flagged, threshold, ask_floor) -> bool
                                                # route_line without cn8_question or cn8_error returns auto_accept
cn8_written_by_rule(confidence: int, threshold: int, single_line: bool) -> bool   # confidence >= threshold, or single
validate_cn8(code, options) -> bool             # ^\d{8}$ and among the CN-8 lines of the decided HS-6
validate_taric10(code, subdivisions) -> bool    # ^\d{10}$ and among the subdivisions
taric_rule(subdivisions, snapshot_loaded) -> Rule        # not_loaded | not_available | trade_defence | auto_completed | choose
code_to_write(rule, subdivisions, cn8_written) -> str|None    # only auto_completed with a written CN-8
TRADE_DEFENCE_CONFIRM = {"551", "552", "553", "554", "555", "570"}
measure_group(measure_type) -> "duties" | "trade_defence" | "requirements"   # fixed table, unknown → requirements
taric_view(subdivisions, origin, snapshot_date, outcome) -> view model         # grouping only; adds, drops or alters nothing
eu_taric_url(code, origin, snapshot_date) -> str      # research R-08
EZT_ONLINE_URL = "https://auskunft.ezt-online.de/ezto/Welcome.do"
```

All are free of model, store and Streamlit imports and are covered by tests written first (Principle VII).

## 3. Line store interface (additions; `agent/store.py`)

```text
set_cn8_result(line_no, choice: Cn8Choice)                 # writes or suggests; records cn8_written / cn8_question; recomputes the route
confirm_cn8(line_no, cn8: str)                             # clerk; validate_cn8; closes an open question; records cn8_written (clerk)
set_taric_result(line_no, outcome: TaricOutcome)           # records taric_written / taric_pending / taric_not_available
confirm_taric10(line_no, code: str)                        # clerk; validate_taric10; requires a written CN-8
ask_shipper_for_taric(line_no, question: str)              # clerk; feature 001's ask-shipper decision; stores the question;
                                                           # records taric_question; writes no TARIC-10
set_taric_origin(code: str) -> str                         # upper-cases and validates ^[A-Z]{2}$, else ValueError; previous origin stays
set_decision (changed): accepting an HS-6 other than the one the CN-8 was chosen under clears the CN-8 choice and TARIC outcome
decided_code(line) (changed): with no clerk decision, it uses hs6_auto_decided (data-model §6)
decided_cn8(line) -> str|None, decided_taric10(line) -> str|None   # written codes, top-down (data-model §6)
counts() gains "cn8_to_confirm" and "taric_to_confirm"     # never added to the route counts
set_threshold(value) also re-evaluates CN-8 choices the clerk has not confirmed, and re-applies code_to_write (no model call)
effective_route(line): an open CN-8 question takes precedence over an HS-6 acceptance (data-model §6)
CSV_COLUMNS gains "cn8", "taric10" at the end; to_json_bytes gains "cn8", "taric10" per line
```

Confirmations raise `UnknownCodeError` for a code outside the options. They raise `LockedError` when the line's HS-6 is
not decided or, for a TARIC-10, when its CN-8 is not written. Feature 001's lock rules are unchanged.

## 4. Agent contract (changes; `agent/agent.py`, `agent/prompts.py`)

- **System prompt**: the tool order for a check request gains:
  - "6. classify_cn8 - chooses the CN-8 under each decided HS-6";
  - "7. lookup_taric - looks up the TARIC subdivisions and measures and applies the rules".

  The model never states a CN-8, TARIC-10, rule or count that is not in a tool result or the context block.
- **Completeness guard** (`_finalize`): after the HS-6 steps, it runs `classify_cn8` for decided lines without a CN-8 choice and `lookup_taric` for lines without a current outcome. These are marked "run by the app".
- **`turn_tools`**: a reply turn still offers only `apply_shipper_reply`; the two steps run once the clerk accepts the new version's HS-6.
- **Clerk actions**: an app-level function `after_hs6_decision(store, kb, line_no)` runs the two steps for one line. The UI starts it as a background job after the clerk accepts or chooses an HS-6, and after a CN-8 confirmation (TARIC step only). The UI never calls the model or retrieval itself.
- **Origin change**: an app-level function `apply_taric_origin(store, kb, code)` calls `set_taric_origin`, then re-runs the lookup and the rules for every line with a CN-8. Subdivision codes do not depend on the origin, so stored suggestions are reused and no model is called (FR-018). Each lookup takes under 1 ms, so it runs synchronously.
- **Display**: `line_taric_view(store, kb, line_no)` looks up the line's CN-8 for the shipment's origin and returns `taric_view`, or None without a CN-8. The UI calls it and never reads `kb.taric` itself (architecture invariant).
- **Context block**: `build_context` gains each line's CN-8, TARIC-10, rule and pending markers, so follow-up answers come from stored results (Principle III).
