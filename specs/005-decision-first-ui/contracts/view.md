# Contract: the view module (`ui/view.py`, `ui/shipper_email.py`)

Everything the two pages show about a line is computed here, from the line store, with no model call and no write.
Both modules are pure: no Streamlit import, no network, no clock.

**What they read**:
- the store's methods: `effective_route`, `decided_code`, `decided_cn8`, `decided_taric10`, `cn8_pending`,
  `taric_pending` and `ready_to_accept`;
- the line records it returns: `line.current` and `line.versions`;
- for kind (b) and the email's TARIC question, the agent's `line_taric_view`.

**They never import the TARIC tool.** tests/unit/test_taric_store.py forbids the tool's name anywhere in `ui/` and
`app.py`.

**Rules for the pages**: they render what these functions return and never re-derive it (FR-010, research R-03). Every
text below is exact, and `{…}` marks a value.

## 1. Line status

`line_status(store, line, activity) -> LineStatus` (data-model §1).
- `activity` is `"running"`, `"queued"`, `"recheck_queued"` or `None`: whether a background job covers this line
  (contracts/ui.md §6). `"recheck_queued"` marks a re-check waiting behind another job; its edit is not stored yet.
- The first matching row of the table below wins.

**Notation**: `v = line.current`, `route = store.effective_route(line)`, `hs6 = store.decided_code(line)[0]`,
`c = v.cn8`, `t = v.taric`, `step = next_step(store, line)`.

**`next_step(store, line)`** names the step a line still waits for, or returns `None`:
- `v.status` is pending: "stop-word check" when `v.flag` is `None`, else "HS-6 step";
- `hs6` is decided and `c` is `None`, or was chosen under another HS-6: "CN-8 step";
- `c` holds a CN-8 chosen under `hs6` (`c.cn8` set, no `c.question`, no `c.error`), and `t` is `None` or was looked up
  for another origin than `store.shipment.taric_origin`: "TARIC step". This reads the same stored fields as the TARIC
  tool's own test, without importing the tool.

| # | Condition | Colour | Text | Action | Kind | Accept control |
|---|---|---|---|---|---|---|
| 1 | `activity` is `"recheck_queued"`, or `activity` set and `step` set | grey | "Queued: re-check", "Running {step}…" or "Queued: {step}" | none | none | none |
| 2 | `v.status` is failed | red | "Check failed" | Update | `c_failed` | locked |
| 3 | `v.status` is pending | grey | "Not checked yet" | none | none | none |
| 4 | `v.flag` is vague or stop word | red | §2.1 | Update | `c` | locked |
| 5 | `v.unreadable` | red | "Ask: unreadable line" | Update | `c` | locked |
| 6 | `route` is `ask_shipper` and `c.question` is set | red | §2.1 | Update | `c` | locked |
| 7 | `route` is `ask_shipper` | red | §2.1 | Update | `c` | locked |
| 8 | `c` is set, `c.error` is set and `c.hs6` is `hs6` | yellow | "Pick: CN-8, {n} lines" | Choose | `a_cn8` | none |
| 9 | `route` is `review` | yellow | §2.2 | Choose | `a_hs6` | none |
| 10 | `step` is "CN-8 step" | yellow | "Pick: CN-8, {n} lines" | Choose | `a_cn8` | none |
| 11 | `store.cn8_pending(line)` | yellow | "Pick: CN-8, {n} lines" | Choose | `a_cn8` | none |
| 12 | `step` is "TARIC step" | yellow | "Confirm: {CN-8}" | Choose | `a_cn8` | none |
| 13 | `store.taric_pending(line)` | yellow | §2.2 | Choose | `b` | none |
| 14 | otherwise | green | "Accepted" or "Ready" | Change | `a_change` | Ready: selectable |

- **Row 3** is transient: a job that ends with an error fails the lines it left pending (contracts/ui.md §6).
- **Row 5**: an unreadable line has no flag, so the store refuses to accept it. It is red with its lock reason
  (Principle VI), and the clerk types what the line says, or asks the shipper (kind (c)).
- **Rows 10 and 12** are reached in two ways:
  - the step after a confirmation did not run, because its job ended with an error;
  - for row 10, the HS-6 was decided without the CN-8 step, for example after the threshold was lowered on
    Admin › Rules.

  The clerk picks or re-confirms the CN-8, and confirming runs the missing TARIC step (research R-15).
- **`{n}` in rows 8, 10 and 11** counts the CN-8 lines under the HS-6: `c.options` when the choice was made under it,
  else `store.index.cn8_lines(hs6)`.
- **Row 14's kind `a_change`** is kind (a) opened on the decided codes (§5). Its TARIC-10 form shows kind (b) when the
  CN-8 has several subdivisions. A green line is never read-only: the clerk can override an automatically accepted
  code (spec clarifications).
- **Accepted**: a green line is Accepted when all three hold:
  - `v.decision` accepts its HS-6;
  - `c.written_by` is clerk;
  - `t.written_by` is clerk, or `t.rule` is `not_available` or `not_loaded`.

  Otherwise it is **Ready**.
- **The dot**: `:green[●]`, `:yellow[●]`, `:red[●]`, `:gray[◌]` (research R-09).

## 2. Texts

- **Status texts** (the Status column) are cut at 44 characters with "…". Lock reasons, questions and reason lines are
  never cut.
- **Codes** in texts use the spaced form: HS-6 "9503 00", CN-8 "8714 91 10", TARIC-10 "7318 15 58 10".

### 2.1 Red lines

**Term-based** means `v.flag.matched_term` is set and `v.flag.rule_source` is not `judgement`. The rule engine gives
an ICS2 match the kind vague, and a firm-list match the kind stop word. The rule label is:
- "ICS2 unacceptable term" for `ics2_unacceptable`, for example "spare parts";
- "ICS2 stop word" for `ics2_stop_words`;
- "firm stop word" for `firm_stop_words`, for example "gift".

| Line | Status text | Reason line (kind c) | Lock reason |
|---|---|---|---|
| Flagged, term-based | "Ask: what exactly is “{term}”?" | "Reason: {rule label} '{term}'" | "Locked: {rule label} '{term}' — update the description and re-check" |
| Flagged by judgement | "Ask: {ask_for, comma-joined, '_' read as a space}?", for example "Ask: material, product name, use?" | §2.3 | "Locked: vague description — update the description and re-check" |
| Unreadable | "Ask: unreadable line" | "Reason: the description could not be read" | "Locked: the description could not be read — update the description and re-check" |
| Open CN-8 question | "Ask: {attribute without a leading "whether "}?" | "Reason: the CN-8 depends on {attribute}, which the description does not state" | "Locked: the CN-8 depends on {attribute} — update the description and re-check" |
| Sent to the shipper, with a TARIC question | "Ask: which TARIC subdivision applies?" | "Reason: you sent this line to the shipper" | "Locked: sent to the shipper — update the description and re-check" |
| Sent to the shipper | "Ask: what exactly are the goods?" | "Reason: you sent this line to the shipper" | "Locked: sent to the shipper — update the description and re-check" |
| Check failed | "Check failed" | "Reason: the check failed — {v.error_reason}" | "Locked: the check failed — re-check the line" |

The full question of a red line is the English question of §7.3. It is shown in kind (c) and used in the English
email.
- `question(store, line, lang, kb) -> str | None` builds it in either language.
- `kb` serves the TARIC question, whose subdivision texts come through `line_taric_view`.
- For a TARIC question in English, it returns the stored question.

### 2.2 Yellow lines

| Line | Text |
|---|---|
| Review, `store.ready_to_accept(line)` | "Confirm: {top HS-6}" |
| Review, no candidate | "Pick: no candidate" |
| Review | "Pick: {n} candidates", "Pick: 1 candidate" (n = candidates shown, at most 3) |
| TARIC-10, one subdivision (trade defence) | "Confirm: {TARIC-10}" |
| TARIC-10, two subdivisions | "Pick: {last two digits} or {last two digits}", for example "Pick: 10 or 90" |
| TARIC-10, more subdivisions | "Pick: {n} options, {k} AD" with k = `len(t.trade_defence)`; "Pick: {n} options" when k is 0 |

### 2.3 Candidates and reasons of a flagged vague line (kind c)

- **The candidates line**: "Candidates: {code} ({conf} %) · {code} ({conf} %) · {code} ({conf} %)". It ends with
  " — too close to call" when the top two confidences differ by at most `CLOSE_POINTS = 10`.
- **The reason line**:
  - a term-based flag gives the reason of §2.1, which always wins;
  - a judgement flag gives "Reason: candidates too close" when the candidates are close as defined above, otherwise
    "Reason: vague description — {v.flag.reason}".
- This is a display rule only; routing never reads it (research R-16).

### 2.4 Running steps

`{step}` is "stop-word check", "HS-6 step", "CN-8 step" or "TARIC step", as `next_step` returns it.

## 3. Code display

`code_display(store, line) -> CodeDisplay`:
- **Known digits**: those of `decided_taric10`, else `decided_cn8`, else `decided_code` (dot removed). A suggestion
  never fills a digit.
- **Layout**: ten slots grouped 4-2-2-2, each unknown digit shown as "_": "____ __ __ __", "9503 00 __ __",
  "8714 91 10 __", "9617 00 00 00".
- **8-digit lines**: with a decided CN-8 and `t.rule` `not_available` or `not_loaded`, the 8 digits in three groups
  ("8714 91 10"), with the note "TARIC not available" or "TARIC not loaded".
- **On the page**: the text as inline code, and the note as a caption under it.

## 4. Summary, bar and email count

`summary(store, statuses) -> Summary`:
- **Counts**:
  - `lines`: every line;
  - `ready`: green; `pick`: yellow;
  - `ask`: red with a question, so every red line except "Check failed";
  - `failed`: "Check failed"; `running`: grey;
  - `to_accept`: green and not Accepted.
- **`seconds`**: the summed `elapsed_s` of `store.shipment.check_runs` whose steps include `check_description`.
  "+ Check one more line" adds its time; a re-check adds none.

`summary_text(summary) -> str`:
- "{lines} lines checked in {seconds:.0f} s · {ready} ready · {pick} need a pick · {ask} need the shipper";
- then " · {failed} check failed" when failed > 0, and " · {running} updating" when running > 0;
- singular forms: "1 line checked", "1 needs a pick", "1 needs the shipper";
- while a check job runs, the page shows "Checking {lines} lines… · {elapsed:.0f} s" instead (contracts/ui.md §3).

`split_bar(summary) -> str`:
- 60 "█" blocks, shared in this order between green (ready), yellow (pick), red (ask + failed) and grey (running);
- split by largest remainder, each non-zero count at least one block;
- the result reads `":green[███…]:yellow[███…]:red[███…]:gray[███…]"`, with empty parts left out.

**Button labels**: "Accept all {to_accept} ready"; "Accept {n} selected"; "Draft shipper email ({ask} lines)", "(1 line)"
or "(0 lines)".

## 5. Kind (a) rows and the HS-6 candidates block

`hs6_rows(store, line) -> list[CandidateRow]`: up to three candidates, in stored order.
- **code**: the HS-6 ("8518 30"), or its single CN-8 line when `store.index.cn8_lines(code)` has exactly one ("9617 00
  00");
- **description**: the subheading text;
- **confidence**: 0–100;
- **rationale**: the candidate's own reasoning, shown as a caption cut at 150 characters with the full text as its help;
- **history_only**: shown as the badge "history only";
- **precedent**: the stored ruling, or `None` ("no close precedent").

**The HS-6 candidates block** (Principle III): `hs6_rows` as Code | Description · precedent | Confidence, each row with
its rationale, under the caption "Confidence is a model estimate, not a calibrated probability." Every expanded row of
a line with candidates shows it:
- as the pick table, in kind `a_hs6` and in the HS-6 form of `a_change`;
- as an expander "HS-6 candidates (model estimate)" in every other kind: open in kind (c), and closed in kinds `a_cn8`
  and `b` and in the CN-8 and TARIC-10 forms of `a_change`, where the HS-6 is already decided.

**"Other HS-6 code…"**: the last Pick row of kind `a_hs6` and of the HS-6 form of `a_change` (feature 001 FR-023).
- Picking it shows a text input with the placeholder "e.g. 8452.90" and at most 7 characters.
- "Confirm" sends the typed code to `store.set_decision`. The store checks it against the loaded nomenclature. The
  decision records `chosen_how` typed, or the candidate the code equals.
- It is never pre-selected.

`cn8_rows(store, line) -> list[CandidateRow]`: every CN-8 line under the decided HS-6, in code order (FR-014's CN-8
form).
- **description**: the whole label path, its parts joined with " › ", wrapped. The last part alone repeats, as
  "Of plastics" does three times under 9503.00;
- **confidence and precedent**: only on the chosen CN-8, and only when it is a model estimate (`c.confidence > 0` and
  more than one option). The other rows show none.

**Pre-selection**:
- `a_hs6`: the top candidate;
- `a_cn8`: `c.cn8` when set, else the first line;
- `a_change`: the decided HS-6 in the HS-6 form, the decided CN-8 in the CN-8 form, and the written TARIC-10 in the
  TARIC-10 form. When the decided HS-6 was typed and is not among the candidates, "Other HS-6 code…" is
  pre-selected, holding it.

**`a_change` has three forms**:
- **HS-6**, the default: `hs6_rows` and "Other HS-6 code…";
- **CN-8**: `cn8_rows`, offered only when the decided HS-6 has more than one CN-8 line;
- **TARIC-10**: kind (b)'s `subdivision_rows` (§6), offered only when the stored TARIC outcome has more than one
  subdivision.

In every form, "Confirm" is disabled while the pick is the decided code. A code the clerk confirms follows:
- for an HS-6, typed or picked, or a CN-8: the flow of kind (a) on a review or CN-8 line (contracts/ui.md §5.1);
- for a TARIC-10: kind (b)'s `confirm_taric10`, with no model call and no job (contracts/ui.md §5.2).

`explain_a(store, line, kind) -> tuple[str, str]`: the two explanation lines of FR-014.
- **First line**:
  - for `a_hs6`, the top candidate's rationale, cut at 200 characters;
  - for `a_cn8`, "The HS-6 is {hs6}; its subheading has {n} CN-8 lines."
- **Second line**:
  - review below the threshold: "Top candidate leads ({conf} %) but is under the {threshold} % auto-accept threshold, so
    you decide. TARIC runs after your pick."
  - ready to accept: "Top candidate leads ({conf} %), but this line was flagged before its update, so it needs your
    confirmation. TARIC runs after your pick."
  - no candidate: "No valid candidate was found. Type the HS-6 code, or ask the shipper what the goods are."
  - CN-8 suggestion below the threshold: "CN-8 to confirm: its confidence ({conf} %) is under the {threshold} %
    threshold. TARIC runs after your pick."
  - CN-8 suggestion against its ruling: "CN-8 to confirm: the cited ruling {ref} classifies under {code}, not this
    CN-8."
  - CN-8 step failed: "The CN-8 step failed: {c.error}. Pick the CN-8."
  - CN-8 step not run (row 10): "No CN-8 was chosen for this HS-6 yet; the CN-8 step did not run, for example after a
    threshold change. Pick the CN-8."
  - TARIC step not run (row 12): "The TARIC step did not finish for this CN-8. Confirm it to look up TARIC again."
- **For `a_change`**:
  - first line: "Decided: HS-6 {hs6}, {how} · CN-8 {cn8}, {how} · TARIC-10 {code}, {how}". For a line that stops at 8
    digits, the last part reads "· TARIC not available" or "· TARIC not loaded";
  - second line, in the HS-6 and CN-8 forms: "Pick another code to override it. The later steps run again after your
    pick."; in the TARIC-10 form, the two lines of `explain_b` instead.

| Code | {how} |
|---|---|
| HS-6 | "auto-accepted at {conf} %" (no decision); "auto-accepted at {conf} %, accepted by you" (`chosen_how` auto); "confirmed by you" (top); "chosen by you" (another candidate); "typed by you" (typed) |
| CN-8 | "confirmed by you" (clerk); "single CN-8 line" (rule, one option); "written by rule at {conf} %" (rule) |
| TARIC-10 | "confirmed by you" (clerk); "auto-completed" (rule) |

## 6. Kind (b) rows

`subdivision_rows(view) -> list[SubdivisionRow]` reads only the agent's `line_taric_view` (feature 004), never
`kb.taric`. For each subdivision:
- **code**: the full code, spaced, "7318 15 58 10";
- **description**: the TARIC text, or "the whole CN-8" for a code ending in 00 with no text;
- **duty**: the duty text of the first type-103 measure. When a preference measure (type 142, 143, 145 or 146)
  applies, " · pref. {its duty}" is added for the first one. Cut at 40 characters.
- **anti-dumping**, from the trade-defence group:
  - percentages are read from the duty texts of types 551–555 with `(\d+(?:\.\d+)?)\s*%`, trailing zeros dropped;
  - one distinct rate: "{rate} % AD"; several: "{lowest}–{highest} % AD";
  - types 551–555 with no percentage, such as the specific duty "172.2 EUR / 1000 kg I": "AD: {first duty text}", cut
    at 32 characters;
  - only type 570: "control";
  - nothing: "none".
- **has_trade_defence**: the subdivision has a type 551–555 or 570 measure;
- **suggested**: it is the stored suggestion.

The page shows the anti-dumping cell in red unless it reads "none".

`explain_b(store, line, view) -> tuple[str, str]`:
- "CN-8 is {CN-8} ({label}). {k} of {n} subdivisions carry anti-dumping or countervailing measures for {origin}.";
  `{label}` is the last two parts of the CN-8's label path, joined with " › ": "Slotted or cross-recessed heads ›
  Other", or "Frames" when the path has one part;
- "Your pick confirms both the CN-8 and the TARIC-10.", followed by one of:
  - " CN-8 written by rule at {conf} %.";
  - " CN-8 confirmed by you.";
  - " Single CN-8 line."

**Pre-selection**: the suggestion when set, else the first subdivision. In the TARIC-10 form of `a_change`, the written
TARIC-10.

`taric_question(view) -> str`: the question that "None of these → ask shipper" stores with
`store.ask_shipper_for_taric`. It is the English question of §7.3 for a TARIC question.

On a green row (`a_change`), the TARIC block shows the row of `subdivision_rows` for the written TARIC-10.

## 7. The shipper email (`ui/shipper_email.py`)

`draft(store, kb, lang) -> EmailDraft`, with `lang` `"en"` or `"zh"`.
- **Lines**: the red lines with a question, in file order. A failed check has no question.
- **Invoice id**: `invoice_id(store)` (§8).
- **Description**: each line's first version's display text, the text the shipper wrote.
- **Text**: the subject, a blank line, then the body, joined with newlines.

### 7.1 English

```text
Subject: Invoice {id} — {C} lines need more detail before customs filing

Dear {shipper},

Thank you for your documents for invoice {id}. Before we can file the ICS2 entry summary declaration with EU customs,
we need more detail on the following {C} goods descriptions:

1. Line {n} “{description}” — {question}
2. …

Please reply with the details for each numbered line. We will file as soon as we have them.

Kind regards,
[Your name] — [Forwarder name], Hamburg
```

- **Singular**: "1 line needs more detail", "the following goods description".
- **No shipper name**: without a name, or with the placeholder "New shipper", the greeting is "Dear Sir or Madam,".

### 7.2 Chinese

```text
主题：发票 {id}：{C} 行货物描述需补充信息后方可报关

{shipper}，您好！

感谢您提供发票 {id} 的单据。在向欧盟海关提交 ICS2 入境摘要申报之前，我们需要您就以下 {C} 项货物描述补充信息：

1. 第 {n} 行“{description}”— {question}
2. …

请按编号逐项回复。收到您的信息后，我们将尽快完成申报。

顺颂商祺！
[经办人姓名] — [货代公司名称]，汉堡
```

- **No shipper name**: the greeting is "您好！".
- **Template text**: every template part is Chinese, apart from the acronyms ICS2 and TARIC.
- **English in data**: English can appear only in data:
  - the shipper's descriptions and name;
  - the invoice id;
  - a matched term quoted from a description;
  - TARIC codes and texts;
  - a model-written CN-8 attribute.

### 7.3 Questions

| Line | English | Chinese |
|---|---|---|
| Open CN-8 question | "Please confirm {attribute}." | "请确认以下信息：{attribute}" |
| Flagged, term-based | "“{term}” is not accepted as a goods description. Please state the exact product name, the material and the intended use." | "“{term}”不能作为货物描述。请说明确切的产品名称、材质和用途。" |
| Flagged by judgement | "The description is too general for customs. Please state the exact product name, the material and the intended use." | "该描述过于笼统，无法用于海关申报。请说明确切的产品名称、材质和用途。" |
| Unreadable | "We could not read this line of your document. Please state the exact product name, the material and the intended use." | "我们无法读取您单据中的这一行。请说明确切的产品名称、材质和用途。" |
| Sent to the shipper, with a TARIC question | "Please state which of these TARIC subdivisions applies: {code} ({text}); {code} ({text})." | "请说明以下哪一个 TARIC 细分适用：{code}（{text}）；{code}（{text}）。" |
| Sent to the shipper | "Please state the exact product name, the material and the intended use." | "请说明确切的产品名称、材质和用途。" |

The TARIC question lists the stored outcome's subdivisions with their TARIC texts, read through `line_taric_view`.

## 8. Other values

- **`invoice_id(store)`**: `shipment.reference` when set, else `shipment.id`, the rule `export_filename` already uses.
  The page sets the reference to the bundled reference for the sample, and to the file name without its extension for
  an upload (contracts/ui.md §2).
- **`origin_toast(message) -> str`**:
  - it reads the agent's `apply_taric_origin` result, "Origin {XX}: the TARIC rules re-applied to {n} line(s)", whose
    format feature 004's tests pin;
  - it returns "Origin {XX} — TARIC rules re-applied to {n} lines, no model call", or "1 line";
  - any other message is returned unchanged.
- **`snapshot_caption(kb) -> str`**: "TARIC snapshot {date}" or "TARIC not loaded", for the header.
- **`taric_statement(kb) -> str`**: for Admin › Data, carrying feature 002 FR-024's mismatch count:
  - "TARIC snapshot: {date} · {n} CN-8 mismatches · Swedish Customs Tariff File Distribution";
  - "1 CN-8 mismatch" in the singular;
  - "TARIC not loaded" without a snapshot.
- **`kb_statement(kb) -> str`**: today's knowledge-base caption, with "updated {kb.updated}" (Principle IV).
- **`md_escape(text) -> str`**: escapes the Markdown characters (`\ * _ [ ] ( ) # + - . ! | > < ~ $ :` and backticks)
  of untrusted text before it goes into a label or Markdown (research R-17). Untrusted text means the descriptions,
  terms, the shipper name, the uploaded file name and model text.
- **`split_description(text) -> tuple[str, str]`**: splits an edited description into Chinese and English with
  `tools.parsers.split_mixed`, as today's chat does for pasted lines.
- **`edit_problem(zh, en) -> str | None`**: "Write the goods description first." when both parts are empty;
  "the Chinese text is over 300 characters" or "the English text is over 300 characters" for a part over
  `MAX_DESC_CHARS`; else `None`. It mirrors `update_description`'s rule, so a queued re-check is checked when it is
  clicked.
- **`audit_csv(store) -> bytes`**: `shipment.audit` as UTF-8 CSV with a BOM, with the columns at, line_no, version_no,
  change, previous, new, actor and note.
- **`quality_rows(history, results) -> list[dict]`**: the Admin › Quality table (contracts/ui.md §8); `[]` when both
  files are missing.
