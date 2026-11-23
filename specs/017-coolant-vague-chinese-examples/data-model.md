# Data Model: Chinese Examples for the Vagueness Check

No entity of the line store changes. Three small structures matter to the tests and the evaluation.

## 1. Example pair (prompt text; spec FR-001 to FR-003)

| Field | Meaning | Rule |
|---|---|---|
| `complete` | a Chinese line that names the goods and states their use and material or composition | listed in the prompt's Chinese acceptable group, exactly once |
| `vague` | a bare generic category term, which may connote a broad class of goods or a material without stating a specific composition or use | listed in the prompt's Chinese vague group, exactly once |
| family | the goods both members are about (for the reader; not in the prompt) | one family per pair |

The four pairs: (铝合金折叠梯，家用 · 金属件), (陶瓷地砖，室内地面用 · 建材), (儿童用的塑料餐具，不含双酚A · 日用百货),
(橡胶密封垫片，水管接头用 · 零部件). Invariants the offline test checks, every comparison on whitespace-normalised text
(`" ".join(s.split())`), as the prompt is a wrapped source string:

- four and four, each member once, the complete ones in the acceptable group and the vague ones in the vague group;
- the sixteen English examples of spec FR-002 present; the prompt with the Chinese sentence cut out hashes to today's
  SHA-256 (`3fc8ad1f0ace606cceaa0c25f03ac3b4a4de5b24d0b09a8ce02c7a67902c8f14`, 1,399 characters, 15 line breaks);
- no member contains 冷却液, 冷却, 切削, 润滑, 乳化, 防冻 or 油;
- no member equals or contains a `description` of `tests/eval/cn8_eval_set.json`, a `text_zh` or `text_en` of
  `tests/eval/hs6_eval_zh.json`, a `text` of `tests/eval/hs6_eval_coolant_set.json`, or a `text` or `original` of
  `tests/eval/hs6_eval_outside_set.json`, nor either half of a bilingual text split at " / ";
- `check_rules(member, "", RuleSet.load(RULES_DIR))` is `None` for every member (the shipped lists under `data/rules/`,
  532 terms; the fixture lists under `tests/fixtures/rules`, 102 terms, may be checked too).

## 2. Coolant-9 (one line of `tests/eval/hs6_eval_coolant_set.json`; spec FR-006, clarification 1)

| Field | Value |
|---|---|
| `id` | `coolant-9` |
| `text` | `金属加工冷却液，不含矿物基础油` |
| `expected_hs6` | `3403.99` |
| `note` | the live-test line of 2026-11-20 (the Chinese half of coolant-6), added by feature 017 |

The file's `built_on` stays `2026-11-18` (research R-05): the rulings eligible to vote for every line are those valid on
that date, as in iteration 9. The line follows coolant-8; the file's `source` field gains "; coolant-9: the live-test
line of 2026-11-20, feature 017"; every other line is unchanged.

## 3. Evaluation rows read for the report (existing format, read only; spec FR-008)

A run's own results file (`tests/eval/hs6_eval_<set>_<tag>_en_expansion-off_wording-off.json`; the 120-line set's has
no `<set>_` part) holds `summary` (the history entry) and `runs`, three lists of rows in the set's order.

- **Set-wide measures** of `summary`: `majority_top1`, `top1_runs`, `routes_runs`, `wrong_auto_runs`, `cost_usd`, the
  `on` block of the precedent override. They count every line of the set, so for the coolant set they include
  coolant-9: SC-003 reads them for the 120-line set; the coolant set's per-run counts compared with iteration 9 are
  recomputed from the rows without coolant-9, or name it.
- **Per-line entries** `summary["lines"]`: `id`, `expected`, `majority`, `right`, and `seen` (each run's `top1` and
  `route`). SC-004's coolant verdict reads `right` of coolant-1 to coolant-8 from here; the outside set's verdict reads
  its 14 entries.
- **Rows** (`runs[k][i]`): `reference`, `flag` (`ok`, `vague`, `stop_word` or `failed`), `route` (`auto_accept`,
  `review`, `ask_shipper`), `top1`, `hit`. SC-001, SC-002 and SC-007 read `flag` and `route` of the coolant lines in
  each run; the flag comparison of FR-008 reads every row's `flag` per set and per run against the baseline runs'
  rows: `tests/eval/hs6_eval_014a-rule-a.json` (120 lines, iteration 21: five lines flagged in every run),
  `tests/eval/hs6_eval_outside_014a-a_en_expansion-off_wording-off.json` (outside, iteration 1: none) and
  `tests/eval/hs6_eval_coolant_014a-rule-a.json` (coolant, iteration 9: coolant-1, -2, -3, -8).
