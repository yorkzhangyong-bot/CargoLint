# Quickstart: validating the CN-8 step, the TARIC rules, the measures and the export

A run guide that proves the feature end to end. Commands are for Git Bash at the repository root, with the project's
`.venv`.
- **Prerequisites**:
  - a built knowledge base: `python -m rag.loader --demo`, or the full EBTI build for vector precedent (research R-02);
  - the schema-2 TARIC snapshot of 2026-10-01 from `python -m rag.loader --taric` (feature 003).
- **Live scenarios** need `OPENROUTER_API_KEY` and spend credits; run them only when the author asks.
- **Where to look**: formats and guarantees are in [contracts/](contracts/), meanings in [data-model.md](data-model.md), and the expected figures in [research.md](research.md).

## Scenarios

| # | Proves | Steps | Expected |
|---|---|---|---|
| A | SC-003, SC-005, SC-006, SC-007 | `pytest -q` | all pass offline: the 432 existing tests, as updated by this feature, and the new ones. The new ones include the four rule tests (auto-complete, choose with suggestion, not available, trade-defence confirmation); not available is proven with fixtures only (research R-16) |
| B | US2, FR-008 to FR-011, on real data | apply `taric_rule` to `TaricStore.from_jsonl("data/taric.jsonl").lookup_taric(cn8, origin)` for the codes of research R-16 | 7318 15 20 → `auto_completed`; 3926 90 97 → `choose` (14 subdivisions); 7318 15 58 → `trade_defence` for CN and `choose` for US; 8714 91 10 → `trade_defence` |
| C | SC-004, FR-013 to FR-015 | `python tests/eval/taric_ui_parity.py` | 20 of 20. For each acceptance code of feature 002 and origin CN, the subdivisions and measures in `taric_view` equal `lookup_taric`'s output, and each measure sits in exactly one group. No key needed |
| D | SC-001, FR-021 (live) | `python tests/eval/run_eval.py --modes hybrid` | flags 20 of 20, no flagged line auto-accepted, HS-6 top-1 at least 10 of 12, top-3 12 of 12 |
| E | FR-003, research R-17 (live) | `python tests/eval/run_eval.py --modes hybrid --sample` | routes as in the updated `data/samples/sample_lines.json`. A line that moved from auto-accept to ask-shipper has a reason naming its CN-8 attribute ("Plastic toy cars": whether a motor is fitted) |
| F | SC-002 (live) | `python tests/eval/cn8_eval.py` | `tests/eval/cn8_eval.json` written; top-1 for at least 60 of the 120 rulings |
| G | SC-008 (live) | `pytest -m live tests/live/test_cost_budget.py`; then `python tests/eval/make_big_list.py --lines 100 && python tests/eval/scale_check.py` | the 12-line sample plus two follow-up questions under €0.10, with the check under 60 s; 100 lines within 5 minutes; `tests/eval/budget.json` and `tests/eval/scale.json` rewritten |
| H | US1 to US5 in the UI | the browser check below | as listed there |

## Browser check

1. Restart the server, since it never reloads `ui/*.py`: `streamlit run app.py`, then open http://localhost:8501.
2. **Check the sample**: use the sample packing list. The status lists `classify_cn8` and `lookup_taric`. The counts show the three routes, then "CN-8 to confirm" and "TARIC-10 to confirm".
3. **"Plastic toy cars"**: if it routes to Ask the shipper, the reason names the motor, and the CN-8 radio lists the 19 lines of 9503 00. Choose 9503 00 95 and confirm. The CN-8 reads "Confirmed by you", and the route reads accepted.
4. **"Aluminium alloy bicycle frames"**: CN-8 8714 91 10 and the note "Trade-defence measures: confirm the subdivision".
   - There are nine subdivisions, three of them with the Trade defence badge.
   - The caption reads "TARIC snapshot 2026-10-01 · origin CN".
   - "EU TARIC" opens the consultation page for the code and CN on 01-10-2026. "EZT-online" opens its start page, with the code and origin shown for copying.
   - Confirm one subdivision: it is written, and the audit trail records the clerk's confirmation.
5. **"Wireless Bluetooth earphones"**: 8518 30 00 is written as the single CN-8 line, and it has two subdivisions. Use "Ask the shipper" with a question. The route reads Ask the shipper, set by you, and the line's `decided_code`, `cn8` and `taric10` are empty in the CSV.
6. **Trade-defence measures in detail**: paste `碳钢十字槽盘头螺钉 M4x10 / Carbon steel cross-recessed pan head screws M4 x 10`, and accept the HS-6 7318.15 if it is not auto-accepted. If the CN-8 is 7318 15 58:
   - each subdivision's trade-defence table lists the anti-dumping rows with their additional codes and "39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %";
   - the requirements table lists 763 and 775 for 1008, All third countries (US3 scenario 1).
7. **Change the origin**: set "Origin (TARIC)" to `US`. The anti-dumping rows for China disappear, and 7318 15 58's note becomes "Choose a subdivision". The TARIC-10 confirmed in step 4 stays. Then enter `C1`: it is refused, and the origin stays US.
8. **Change the threshold**: set it to 99. CN-8 codes written by rule below 99 return to "CN-8 to confirm", together with any TARIC-10 auto-completed from them. Codes you confirmed stay.
9. **Export**: download the CSV. Its header ends with `note,cn8,taric10`, and each code is filled only where it is written.
