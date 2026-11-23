# Backlog

Future work, in priority order. Each entry is a short sketch, not a spec; run it through Spec Kit when it is picked up.

1. **013 Knowledge base refresh.** Done, merged in PR #4. Two scripts download current TARIC and EBTI data, rebuild the store and publish a release per kind; the app shows both snapshot dates, with a warning when the TARIC snapshot is older than 40 days or the EBTI rulings older than 45 days.

2. **014a Retrieval and evidence.** Done, merged in PR #10. Every chapter is indexed (123,531 rulings in 95 chapters). The vote over every chapter decides the auto-accept, and the vote within the candidates' chapters can only send a line to review. Block 3's captions show that veto, "No relevant rulings found" and "No rulings indexed for chapter NN"; block 2 notes a cited ruling that classifies under another code or was not retrieved. The customs-wording rewrite is behind a switch, off by default, and a vague line always asks the shipper. HS-6 result (majority right): 120 lines 84 → 77 with 9 wrong auto-accepts against 10 (SC-004 passes); coolant 6/8 → 8/8; outside set 12/14.

3. **014b Model output.** Changes the prompt and needs eval runs. Goal: win back the 7 lines lost on the 120-line set (84 → 77 in 014a); their causes are in `docs/reports/014a-regression-analysis.md`, section 1.

   - **Reason per candidate.** Add a one- or two-sentence reason per candidate code, shown in the expanded row and included in the CSV export so each row is audit-ready.
   - **Subheading consistency check.** A description that says "without mineral oil" must not get a subheading defined as containing petroleum oils (3403.19 was given at 95 % instead of 3403.99), and the confidence must drop when the check fails.
   - **Subdivision by use.** When the description names the use, rank the matching TARIC subdivision first, e.g. 2710 19 91 metal-working compounds for a coolant with more than 70 % mineral oil.

   **Note:** run the eval set after 014a ships and decide this entry's scope from the remaining errors.

4. **Line-specific shipper questions.** Shipper questions must be specific to the line, not generic. If the material is already given, ask for what is missing, e.g. for a coolant the intended use and whether mineral oil is the basic constituent.

5. **015 Input guardrails.** Cap file size at about 2 MB and lines at about 200 per check, add a cheap no-model relevance check that stops files that do not look like an invoice or packing list, count a daily line budget across all inputs (file upload, single-line check, re-checks) with a "demo limit reached" message, and add a short cooldown between checks per session.

   **Milestone after 013-015:** remove the password and open the demo link publicly.

6. **UI language switch EN / DE / 中文.** Let the clerk switch the screen language, needed for Chinese-owned forwarders in Hamburg as the first target customers.

7. **One text input for one or many lines.** The "Check a single line" tab becomes one box that accepts either a single goods description or a free-text message from a shipper (Chinese, English or mixed, e.g. "two coolants, codes 2710199900 and 3403990000, one with more than 70% mineral oil, one without mineral base oil"). A cheap rule decides first: short text with no list markers, no "one ... one ..." pattern and at most one code is treated as one line with no extra model call; otherwise one model call splits it into goods lines (description, material, use, quantity, shipper's stated code). All resulting lines go straight into the existing result list and are checked as usual, with no confirmation table. A wrong split is fixed with the existing edit-description and re-check. Add one small control: delete a line. If the shipper stated a code, compare its first six digits with the suggested HS-6 and show "matches" or "differs, please check".

8. **TARIC subdivision descriptions.** Show the text of the 8- and 10-digit subdivisions, not only the code.

9. **Multi-file upload.** Check the invoice and packing list of one shipment in a single check, with a file column.

10. **Eval-set fixes.** Review and correct mislabelled lines in `tests/eval`. Add six lines from the user test on two metal-working coolants, with their expected results:

    - `冷却液 矿物油含量大于70%` → 2710.19
    - `没有矿物基础油的冷却液` → ask shipper for the intended use (3820.00 if engine coolant, 3403.99 if metal-working)
    - `金属加工用的冷却液，不含矿物油` → 3403.99
    - `coolant without mineral base oil, for metal working` → 3403.99
    - `金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum mineral oil content more than 70% by weight` → 2710.19 (CN 2710 19 91)
    - `金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral base oil` → 3403.99

    In the outside set (`tests/eval/hs6_eval_outside_set.json`), add Chinese versions of some lines, and mark the bike U-lock as contested (8301.10 or 8301.40): its source ruling (FRBTIFR-BTI-2026-00308) gives 8301.10, while the model and 4 of its 5 nearest rulings give 8301.40.

11. **Admin override slider.** Expose the accept/review confidence threshold as an admin slider.

12. **Shipper memory.** Remember a shipper's earlier answers and reuse them.

13. **stderr logging for the cloud demo.**

14. **Paid hosting on an EU server.** Hetzner with Docker and Caddy and an EU model endpoint, checking OpenRouter data privacy first. Once hosting allows the full store, drop the 5,000-ruling limit (`CARGOLINT_EBTI_RULINGS`) and the eval-code preference in `rag/demo_store.py` (`preferred_codes`, `SAMPLE_VARIANT_HS6`), which gives up to half of the demo store to the CN-8 eval set's and the sample files' HS-6 codes.

15. **Constitution wording.** The governance paragraph still names feature 005 wireframes; wording-only amendment.

16. **Clear messages for permanent model errors.** A permanent OpenRouter error, such as a 404 "0 endpoints out of 1 requested are available matching your guardrail restrictions and data policy" or a 401, is shown to the clerk as "Temporary problem talking to the model; retrying.", and its message is cut off (`ui/jobs.py` keeps 160 characters); a 403 gets a generic refusal text without the provider's message. Classify the non-retryable provider errors (404, 401, 403, guardrail or data-policy refusals) as configuration errors in `agent/llm.py`'s `classify_error`, shown with their full message and no promise of a retry, and keep "temporary" for 429 and 5xx. Found on 2026-11-19 in PR #10's browser tests, where the CI key's guardrail refused the model.

17. **Coolant vague false positive (do before 014b).** Done in feature 017 (branch `017-coolant-vague-chinese-examples`; the pull request's number is added after the merge): four pairs of Chinese examples in the vagueness judgement's prompt, nothing else. Measured on 2026-11-23, three runs per set with Gemini 2.5 Flash: the live-test line (now coolant-9 in the coolant set) and coolant-3 are no longer flagged vague and route by the vote (review in every run); coolant-1, coolant-2 and plain `冷却液` are still flagged vague and ask the shipper in every run; no regression: 120 lines 78/120 on majority (77 before) with the same 3 wrong auto-accepts by majority per line, coolant set 8/8 (9/9 with coolant-9), outside set 12/14; flags against the baseline runs: coolant-3 and two English lines of the 120-line set (IEBTIIENEN004-2025-BTI249, IEBTIIENEN004-2026-BTI124) lost their vague flag, no line gained one (`specs/017-coolant-vague-chinese-examples/eval-report.md`). Still open, with item 4: `ask_for` is not line-specific (below). Original entry: `金属加工冷却液，不含矿物基础油` gets the right code (3403.99) but routes to ask the shipper: the model judges it vague and the shipper question then asks for the material and the use the line already states. The flag is the model's vagueness judgement, not a stop-word rule (`tools/check_description.py:53–57`). `ask_for` always includes material, product name and use (`rag/rules.py:17`, `tools/check_description.py:55`) and the system prompt names all three for every flagged line (`agent/prompts.py:45–46`). Tighten the judgement prompt so a line that states the use and the material or composition is not judged vague, and make `ask_for` line-specific (ties to item 4). Coolant-1 (`冷却液 矿物油含量大于70%`) still needs the intended use to choose between 2710.19 and 3403.99; coolant-3 (`金属加工用的冷却液，不含矿物油`) states the use and composition and is a false positive. The bilingual coolant-6 routed to review in the 014a eval runs, but the Chinese-only live line routed to ask the shipper — the same goods, inconsistent. Found on 2026-11-20 in the live test after 014a.

    - **Language effect.** No list in `data/rules/` holds 冷却液, and the deterministic check gives no rule for any coolant line. The model's judgement flags every Chinese-only coolant line (coolant-1, -2, -3 and -8, in all 15 stored Gemini runs); the same facts with English or German text pass (coolant-4 to -7). Under today's FR-009 ("material **or** use"), coolant-3 and the live line should already pass. The 120-line and outside eval sets hold no Chinese-only line, so add some.
    - **Cause and fix.** The flag comes from the model's vagueness check, not from the stop-word list, and the check's examples (`tools/check_description.py:28–31`) are English only. Proposed fix: add Chinese vague and complete examples.
    - **UI.** Block 1 labels the judgement "Stop-word check" (`ui/expand.py:191`). The vague cap of 59 ties the candidates, so the reason line shows "candidates too close" instead of the model's reason (`ui/view.py:247`). Fix the label, and show the vagueness reason.
    - **Approach** (superseded by feature 017, which added examples only). The judgement returns the composition and the use as verbatim quotes. Code checks that each quote is in the line and decides; a flag that stays cites what is missing (FR-010). List flags (FR-008) stay deterministic. Only the line's own current text counts, never shipper history or the 014a customs-wording rewrite. Asking only for what is missing changes FR-011 and needs a PATCH clarification of constitution Principle III; no other amendment is needed.
    - **Open decisions for the author** (superseded by feature 017, examples only; still open in product terms). Both the material or composition and the use, or either one; whether a negative composition ("不含矿物油") counts; whether single-term list flags are included.
    - **Measurement.** A paid eval on the coolant, 120-line and outside sets plus new Chinese-only lines, with the configured chat model. Targets: no new wrong auto-accept; the complete coolant lines pass, so the live line and coolant-3 leave "ask the shipper"; coolant-1, -2 and plain `冷却液` (coolant-8) stay flagged and still ask the shipper; coolant-1 asks for the use only.

18. **TARIC control-measure conditions are dropped.** Conditional import controls are shown as unconditional requirements. `9004 10 91 00` origin CN shows "Import control - CITES" with no condition, but the source measure (`data/raw/taric/Measure.xml`, SID 4023124) has three conditions (condition Y): a C400 CITES certificate for goods of a CITES-listed species (action 29, import allowed after control), exemption Y900 for goods not concerned by CITES (also action 29), and a third with no document (action 09, import not allowed), plus footnote CD 370. The extractor drops conditions without a duty component (`rag/taric_extract.py:333` renders only conditions that carry a duty expression) and the snapshot stores only a `duty` string (`rag/taric.py:59–73`), so all 699 CITES measures have empty duty; other control measures (745 cat/dog fur, 746 seal products, 748 mercury, 755 waste) are affected the same way. Store conditions, certificates, exemption codes and footnotes in the snapshot and show them in block 4, with the text built from each measure's conditions, e.g. "allowed with C400 (CITES certificate) or Y900 (goods not concerned by CITES); otherwise not allowed", or for a C400-only measure "allowed only with C400; otherwise not allowed". Of the 699 CITES measures, 33 allow import only with C400, with no Y900 (e.g. primates 0106 11 and caviar 1604 31), so a fixed CITES sentence is wrong for them. Found on 2026-11-20 in the live test after 014a (pair with the coolant false-positive entry above).

    - **Cause.** Feature 002's recorded decision (research R-03, "Not read: conditions, exclusions, footnotes"; R-08, conditions without a duty "add nothing"). The display is bound by feature 004 FR-013 (measures shown exactly as returned) and feature 012 D16 ("no certificate claim"). All three must change.
    - **Scale.** 15,307 of 17,876 import requirement measures carry conditions, and the snapshot keeps none of the conditions. "Import control - CITES" shows on 1,237 of 16,752 TARIC-10 codes for origin CN.
    - **Texts.** Certificate texts need the Certificate object, and footnote CD 370's text needs the Footnote object. Neither is loaded today.
    - **Interim.** A caption under "Requirements" saying that the controls apply under conditions, with the EU TARIC link.

19. **Cleanup.** Retire `ASK_FLOOR`: it no longer routes since 014a's vague rule, but the setting and its `ask_floor` parameter remain, in about 50 call sites and in the eval history format. Update the twelve-chapter list in `CargoLint_Project_Intro.md` §10.
