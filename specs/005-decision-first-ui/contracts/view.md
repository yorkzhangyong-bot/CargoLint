# Contract: the view module (`ui/view.py`, `ui/shipper_email.py`)

Everything the two pages show about a line is computed here, from the line store, with no model call and no write.
Both modules are pure: no Streamlit import, no network, no clock. They read the store only through its methods and the
line records it returns (`effective_route`, `decided_code`, `decided_cn8`, `decided_taric10`, `cn8_pending`,
`taric_pending`, `ready_to_accept`, `line.current`, `line.versions`). The pages render what these functions return and
never re-derive it (FR-010, research R-03). Every text below is exact; `{…}` marks a value.

## 1. Line status

`line_status(store, line, activity) -> LineStatus` (data-model §1). `activity` is `"running"`, `"queued"` or `None`:
whether a background job covers this line (contracts/ui.md §6). The first matching row wins.

Notation: `v = line.current`, `route = store.effective_route(line)`, `hs6 = store.decided_code(line)[0]`,
`c = v.cn8`, `t = v.taric`, `step = next_step(store, line)`.

`next_step(store, line)` names the step a line still waits for, or `None`:
- `v.status` is pending: "stop-word check" when `v.flag` is `None`, else "HS-6 step";
- `hs6` is decided and `c` is `None` or was chosen under another HS-6: "CN-8 step";
- `tools.lookup_taric.needs_taric(store, line)` returns a CN-8: "TARIC step".

| # | Condition | Colour | Text | Action | Kind | Accept control |
|---|---|---|---|---|---|---|
| 1 | `activity` set and `step` set | grey | "Running {step}…", or "Queued: {step}" | none | none | none |
| 2 | `v.status` is failed | red | "Check failed" | Update | `c_failed` | locked |
| 3 | `v.status` is pending | grey | "Not checked yet" | none | none | none |
| 4 | `v.flag` is vague or stop word | red | §2.1 | Update | `c` | locked |
| 5 | `route` is `ask_shipper` and `c.question` is set | red | §2.1 | Update | `c` | locked |
| 6 | `route` is `ask_shipper` | red | §2.1 | Update | `c` | locked |
| 7 | `c` is set and `c.error` is set | yellow | "Pick: CN-8, {n} lines" | Choose | `a_cn8` | none |
| 8 | `route` is `review` | yellow | §2.2 | Choose | `a_hs6` | none |
| 9 | `step` is "CN-8 step" | yellow | "Pick: CN-8, {n} lines" | Choose | `a_cn8` | none |
| 10 | `store.cn8_pending(line)` | yellow | "Pick: CN-8, {n} lines" | Choose | `a_cn8` | none |
| 11 | `step` is "TARIC step" | yellow | "Confirm: {CN-8}" | Choose | `a_cn8` | none |
| 12 | `store.taric_pending(line)` | yellow | §2.2 | Choose | `b` | none |
| 13 | otherwise | green | "Accepted" or "Ready" | Change | `a_change` | Ready: selectable |

- Row 3 is transient: a job that ends with an error fails the lines it left pending (contracts/ui.md §6).
- Rows 9 and 11 are reached only when the background step after a confirmation did not run (its job ended with an
  error). The clerk picks or re-confirms the CN-8, which runs the missing step again (research R-15).
- In rows 7, 9 and 10, `{n}` counts the CN-8 lines under the HS-6: `c.options` when the choice was made under it,
  else `store.index.cn8_lines(hs6)`.
- Row 13's kind `a_change` is kind (a) opened on the decided codes (§5). Its TARIC-10 form shows kind (b) when the
  CN-8 has several subdivisions. A green line is never read-only: the clerk can override an automatically accepted
  code (spec clarifications).
- A green line is **Accepted** when `v.decision` accepts its HS-6, `c.written_by` is clerk, and `t.written_by` is
  clerk or `t.rule` is `not_available` or `not_loaded`. Otherwise it is **Ready**.
- The dot: `:green[●]`, `:yellow[●]`, `:red[●]`, `:gray[◌]` (research R-09).

## 2. Texts

All short texts are cut at 44 characters with "…" (the Status column is narrow). The full texts appear in the expanded
row. Codes in texts use the spaced form: HS-6 "9503 00", CN-8 "8714 91 10", TARIC-10 "7318 15 58 10".

### 2.1 Red lines

"Term-based" means `v.flag.matched_term` is set and `v.flag.rule_source` is not `judgement`. The rule label is "ICS2
stop word" (`ics2_stop_words`), "ICS2 unacceptable term" (`ics2_unacceptable`) or "firm stop word" (`firm_stop_words`).

| Line | Status text | Reason line (kind c) | Lock reason |
|---|---|---|---|
| Flagged, term-based | "Ask: what exactly is “{term}”?" | "Reason: {rule label} '{term}'" | "Locked: {rule label} '{term}' — update the description and re-check" |
| Flagged by judgement | "Ask: {ask_for, comma-joined}?", or "Ask: material, product, use?" when empty | §2.3 | "Locked: vague description — update the description and re-check" |
| Open CN-8 question | "Ask: {attribute without a leading "whether "}?" | "Reason: the CN-8 depends on {attribute}, which the description does not state" | "Locked: the CN-8 depends on {attribute} — update the description and re-check" |
| Sent to the shipper, with a TARIC question | "Ask: {question}" | "Reason: you sent this line to the shipper" | "Locked: sent to the shipper — update the description and re-check" |
| Sent to the shipper | "Ask: what exactly are the goods?" | "Reason: you sent this line to the shipper" | "Locked: sent to the shipper — update the description and re-check" |
| Check failed | "Check failed" | "Reason: the check failed — {v.error_reason}" | "Locked: the check failed — re-check the line" |

The full question of a red line, shown in kind (c) and used in the English email, is the English question of §4.3.

### 2.2 Yellow lines

| Line | Text |
|---|---|
| Review, `store.ready_to_accept(line)` | "Confirm: {top HS-6}" |
| Review, unreadable line | "Pick: unreadable line" |
| Review, no candidate | "Pick: no candidate" |
| Review | "Pick: {n} candidates", "Pick: 1 candidate" (n = candidates shown, at most 3) |
| TARIC-10, one subdivision (trade defence) | "Confirm: {TARIC-10}" |
| TARIC-10, two subdivisions | "Pick: {last two digits} or {last two digits}", for example "Pick: 10 or 90" |
| TARIC-10, more subdivisions | "Pick: {n} options, {k} AD" with k = `len(t.trade_defence)`; "Pick: {n} options" when k is 0 |

### 2.3 Close candidates (kind c of a vague line)

- The candidates line reads "Candidates: {code} ({conf} %) · {code} ({conf} %) · {code} ({conf} %)".
- When the top two confidences differ by at most `CLOSE_POINTS = 10`, it ends with " — too close to call" and the
  reason reads "Reason: candidates too close".
- Otherwise the reason reads "Reason: vague description — {v.flag.reason}".
- This is a display rule only; routing never reads it (research R-16).

### 2.4 Running steps

`{step}` is "stop-word check", "HS-6 step", "CN-8 step" or "TARIC step", as `next_step` returns it.

## 3. Code display

`code_display(store, line) -> CodeDisplay`:
- The known digits are those of `decided_taric10`, else `decided_cn8`, else `decided_code` (dot removed). A
  suggestion never fills a digit.
- Ten slots grouped 4-2-2-2; each unknown digit is "_": "____ __ __ __", "9503 00 __ __", "8714 91 10 __",
  "9617 00 00 00".
- With a decided CN-8 and `t.rule` `not_available` or `not_loaded`: the 8 digits in three groups, "8714 91 10", and the
  note "TARIC not available" or "TARIC not loaded".
- The page shows the text as inline code, and the note as a caption under it.

## 4. Summary, bar and email count

`summary(store, statuses) -> Summary`:
- `lines`: every line. `ready`: green. `pick`: yellow. `ask`: red with a question (every red line except "Check
  failed"). `failed`: "Check failed". `running`: grey. `to_accept`: green and not Accepted.
- `seconds`: the summed `elapsed_s` of `store.shipment.check_runs` whose steps include `check_description`. So
  "+ Check one more line" adds its time, and a re-check adds none.

`summary_text(summary) -> str`:
- "{lines} lines checked in {seconds:.0f} s · {ready} ready · {pick} need a pick · {ask} need the shipper";
- then " · {failed} check failed" when failed > 0, and " · {running} updating" when running > 0;
- singular forms: "1 line checked", "1 needs a pick", "1 needs the shipper";
- while a check job runs, the page shows "Checking {lines} lines… · {elapsed:.0f} s" instead (contracts/ui.md §3).

`split_bar(summary) -> str`: 60 "█" blocks shared between green (ready), yellow (pick), red (ask + failed) and grey
(running), in that order, by largest remainder, each non-zero count at least one block:
`":green[███…]:yellow[███…]:red[███…]:gray[███…]"`, with empty parts left out.

Button labels: "Accept all {to_accept} ready"; "Accept {n} selected"; "Draft shipper email ({ask} lines)", "(1 line)",
"(0 lines)".

## 5. Kind (a) rows

`hs6_rows(store, line) -> list[CandidateRow]`: up to three candidates in stored order.
- code: the HS-6 ("8518 30"), or its single CN-8 line when `store.index.cn8_lines(code)` has exactly one ("9617 00
  00");
- description: the subheading text;
- confidence: 0–100;
- precedent: the stored ruling, or `None` ("no close precedent").

`cn8_rows(store, line) -> list[CandidateRow]`: the CN-8 lines under the HS-6, in code order.
- description: the last part of the label path (after the last " > ");
- confidence and precedent: only on the chosen CN-8, and only when it is a model estimate (`c.confidence > 0` and more
  than one option); the other rows show none.

Pre-selection:
- `a_hs6`: the top candidate;
- `a_cn8`: `c.cn8` when set, else the first line;
- `a_change`: the decided HS-6 in the HS-6 form, the decided CN-8 in the CN-8 form, the written TARIC-10 in the
  TARIC-10 form.

`a_change` has three forms:
- **HS-6** (the default): `hs6_rows`;
- **CN-8**: `cn8_rows`, offered only when the decided HS-6 has more than one CN-8 line;
- **TARIC-10**: kind (b)'s `subdivision_rows` (§6), offered only when the stored TARIC outcome has more than one
  subdivision.

In every form, "Confirm" is disabled while the pick is the decided code. A code the clerk confirms follows:
- for an HS-6 or a CN-8, the flow of kind (a) on a review or CN-8 line (contracts/ui.md §5.1);
- for a TARIC-10, kind (b)'s `confirm_taric10`, with no model call and no job (contracts/ui.md §5.2).

`explain_a(store, line, kind) -> tuple[str, str]`: the two explanation lines of FR-014.
- **First line**:
  - for `a_hs6`, the top candidate's rationale, cut at 200 characters;
  - for `a_cn8`, "The HS-6 is {hs6}; its subheading has {n} CN-8 lines."
- **Second line**:
  - review below the threshold: "Top candidate leads ({conf} %) but is under the {threshold} % auto-accept threshold, so
    you decide. TARIC runs after your pick."
  - ready to accept: "Top candidate leads ({conf} %), but this line was flagged before its update, so it needs your
    confirmation. TARIC runs after your pick."
  - no candidate: "No valid candidate was found. Ask the shipper what the goods are."
  - CN-8 suggestion below the threshold: "CN-8 to confirm: its confidence ({conf} %) is under the {threshold} %
    threshold. TARIC runs after your pick."
  - CN-8 suggestion against its ruling: "CN-8 to confirm: the cited ruling {ref} classifies under {code}, not this
    CN-8."
  - CN-8 step failed: "The CN-8 step failed: {c.error}. Pick the CN-8."
  - the TARIC step did not run: "The TARIC step did not finish for this CN-8. Confirm it to look up TARIC again."
- **For `a_change`**:
  - first line: "Decided: HS-6 {hs6}, {how} · CN-8 {cn8}, {how} · TARIC-10 {code}, {how}". The last part reads
    "· TARIC not available" or "· TARIC not loaded" for a line that stops at 8 digits;
  - second line, in the HS-6 and CN-8 forms: "Pick another code to override it. The later steps run again after your
    pick."; in the TARIC-10 form, the two lines of `explain_b` instead.

| Code | {how} |
|---|---|
| HS-6 | "auto-accepted at {conf} %" (no decision); "auto-accepted at {conf} %, accepted by you" (`chosen_how` auto); "confirmed by you" (top); "chosen by you" (another candidate or a typed code) |
| CN-8 | "confirmed by you" (clerk); "single CN-8 line" (rule, one option); "written by rule at {conf} %" (rule) |
| TARIC-10 | "confirmed by you" (clerk); "auto-completed" (rule) |

## 6. Kind (b) rows

`subdivision_rows(view) -> list[SubdivisionRow]` reads only the agent's `line_taric_view` (feature 004), never
`kb.taric`. For each subdivision:
- **code**: shown as its last four digits, "… 10 99", next to the full code in the "All measures" block;
- **description**: the TARIC text, or "the whole CN-8" for a code ending in 00 with no text;
- **duty**: the duty text of the first type-103 measure. When a preference measure (type 142, 143, 145 or 146)
  applies, " · pref. {its duty}" is added for the first one. Cut at 40 characters.
- **anti-dumping**, from the trade-defence group:
  - percentages are read from the duty texts of types 551–555 with `(\d+(?:\.\d+)?)\s*%`, trailing zeros dropped;
  - one distinct rate: "{rate} % AD"; several: "{lowest}–{highest} % AD";
  - types 551–555 with no percentage (a specific duty such as "172.2 EUR / 1000 kg I"): "AD: {first duty text}", cut at
    32 characters;
  - only type 570: "control";
  - nothing: "none".
- **has_trade_defence**: the subdivision has a type 551–555 or 570 measure;
- **suggested**: it is the stored suggestion.

The page shows the anti-dumping cell in red unless it reads "none".

`explain_b(store, line, view) -> tuple[str, str]`:
- "CN-8 is {CN-8} ({label}). {k} of {n} subdivisions carry anti-dumping or countervailing measures for {origin}.";
- "Your pick confirms both the CN-8 and the TARIC-10." followed by one of:
  - " CN-8 written by rule at {conf} %.";
  - " CN-8 confirmed by you.";
  - " Single CN-8 line."

Pre-selection: the suggestion when set, else the first subdivision. In the TARIC-10 form of `a_change`, the written
TARIC-10.

On a green row (`a_change`), the TARIC block shows the row of `subdivision_rows` for the written TARIC-10.

## 7. The shipper email (`ui/shipper_email.py`)

`draft(store, lang) -> EmailDraft`, with `lang` `"en"` or `"zh"`.
- **Lines**: the red lines with a question, in file order.
- **Invoice id**: `invoice_id(store)` (§8).
- **Description**: each line's first version's display text, which is the text the shipper wrote.
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

Singular: "1 line needs more detail", "the following goods description". Without a shipper name, or with the
placeholder "New shipper", the greeting is "Dear Sir or Madam,".

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

Without a shipper name the greeting is "您好！". Every template part is Chinese. The only English text that can appear
is the shipper's own description, a matched term quoted from it, and a model-written CN-8 attribute.

### 7.3 Questions

| Line | English | Chinese |
|---|---|---|
| Open CN-8 question | "Please confirm {attribute}." | "请确认以下信息：{attribute}" |
| Flagged, term-based | "“{term}” is not accepted as a goods description. Please state the exact product name, the material and the intended use." | "“{term}”不能作为货物描述。请说明确切的产品名称、材质和用途。" |
| Flagged by judgement | "The description is too general for customs. Please state the exact product name, the material and the intended use." | "该描述过于笼统，无法用于海关申报。请说明确切的产品名称、材质和用途。" |
| Sent to the shipper, with a TARIC question | "Please confirm: {question}" | "请确认以下信息：{question}" |
| Sent to the shipper | "Please state the exact product name, the material and the intended use." | "请说明确切的产品名称、材质和用途。" |

## 8. Other values

- `invoice_id(store)`: `shipment.reference` when set, else `shipment.id`. This is the rule `export_filename` already
  uses. The page sets the reference to the bundled reference for the sample, and to the file name without its
  extension for an upload (contracts/ui.md §2).
- `origin_toast(message) -> str`: reads the agent's `apply_taric_origin` result, "Origin {XX}: the TARIC rules
  re-applied to {n} line(s)" (pinned by feature 004's tests), and returns "Origin {XX} — TARIC rules re-applied to {n}
  lines, no model call", or "1 line". Any other message is returned unchanged.
- `md_escape(text) -> str`: escapes the Markdown characters (`\ * _ [ ] ( ) # + - . ! | > < ~ $ :` and backticks) of
  untrusted text (descriptions, terms, the shipper name, model text) before it goes into a label or Markdown
  (research R-17).
- `split_description(text) -> tuple[str, str]`: splits an edited description into Chinese and English with
  `tools.parsers.split_mixed`, as today's chat does for pasted lines.
- `audit_csv(store) -> bytes`: `shipment.audit` as UTF-8 CSV with a BOM, with the columns at, line_no, version_no,
  change, previous, new, actor and note.
- `quality_rows(history, results) -> list[dict]`: the Admin › Quality table (contracts/ui.md §8); `[]` when both files
  are missing.
