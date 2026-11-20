# Backlog

Future work, in priority order. Each entry is a short sketch, not a spec; run it through Spec Kit when it is picked up.

1. **013 Knowledge base refresh.** Done, merged in PR #4. Two scripts download current TARIC and EBTI data, rebuild the store and publish a release per kind; the app shows both snapshot dates, with a warning when the TARIC snapshot is older than 40 days or the EBTI rulings older than 45 days.

2. **014a Retrieval and evidence.** Does not change the prompt; changes the rulings fed into it.

   - **Index all chapters.** The EBTI store currently covers only twelve indexed chapters, so goods in other chapters (e.g. 27 and 34 for metal-working coolants and lubricants) have no rulings at all. `refresh_ebti` and the loader index rulings from every chapter, with the chapter list as a setting whose default is all; the demo store keeps `CARGOLINT_EBTI_RULINGS=5000`.
   - **Chapter-filtered retrieval.** Search the nearest rulings only within the chapters of the model's HS-6 candidates, so a coolant (2710, 3403) never matches cooling machinery in chapter 84.
   - **No relevant rulings.** Show "no rulings indexed for chapter NN" when a candidate's chapter is not indexed, or "no relevant rulings found" when no relevant ruling is found, instead of "0 of 5 agree".
   - **Precedent mismatch check.** The model sometimes cites a ruling that does not match the candidate code. Compare each ruling the model cites with that ruling's real code and drop or flag mismatches.
   - **Customs wording.** Rewrite the description into customs wording before embedding. "Coolant" currently pulls rulings on cooling machinery (headings 8419, 8414, 8424, 7309).

   **Note:** run the eval set before and after, and compare HS-6 accuracy.

3. **014b Model output.** Changes the prompt and needs eval runs.

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

11. **Admin override slider.** Expose the accept/review confidence threshold as an admin slider.

12. **Shipper memory.** Remember a shipper's earlier answers and reuse them.

13. **stderr logging for the cloud demo.**

14. **Paid hosting on an EU server.** Hetzner with Docker and Caddy and an EU model endpoint, checking OpenRouter data privacy first.

15. **Constitution wording.** The governance paragraph still names feature 005 wireframes; wording-only amendment.

16. **Clear messages for permanent model errors.** A permanent OpenRouter error, such as a 404 "0 endpoints out of 1 requested are available matching your guardrail restrictions and data policy" or a 401, is shown to the clerk as "Temporary problem talking to the model; retrying.", and its message is cut off (`ui/jobs.py` keeps 160 characters); a 403 gets a generic refusal text without the provider's message. Classify the non-retryable provider errors (404, 401, 403, guardrail or data-policy refusals) as configuration errors in `agent/llm.py`'s `classify_error`, shown with their full message and no promise of a retry, and keep "temporary" for 429 and 5xx. Found on 2026-11-19 in PR #10's browser tests, where the CI key's guardrail refused the model.

17. **TARIC control-measure conditions are dropped.** Conditional import controls are shown as unconditional requirements. `9004 10 91 00` origin CN shows "Import control - CITES" with no condition, but the source measure (`data/raw/taric/Measure.xml`, SID 4023124) has three conditions: a C400 CITES permit for goods of a CITES-listed species (condition Y, action 09), exemption Y900 for goods not concerned by CITES (action 29), and footnote CD 370. The extractor drops conditions without a duty component (`rag/taric_extract.py:333` renders only conditions that carry a duty expression) and the snapshot stores only a `duty` string (`rag/taric.py:59–73`), so all 699 CITES measures have empty duty; other control measures (745 cat/dog fur, 746 seal products, 748 waste) are affected the same way. Store conditions, certificates, exemption codes and footnotes in the snapshot and show them in block 4, e.g. "CITES import control: only for goods of CITES-listed species; otherwise exemption Y900". Found on 2026-11-20 in the live test after 014a (pair with the coolant false-positive entry above).
