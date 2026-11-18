# Backlog

Future work, in priority order. Each entry is a short sketch, not a spec; run it through Spec Kit when it is picked up.

1. **013 Knowledge base refresh.** EBTI rulings and TARIC data are frozen in demo-store-v1. Add a script that downloads current EBTI and TARIC data, rebuilds the vector store, publishes a new release, and shows the snapshot date in the app with a warning when it is older than 30 days.

2. **014 Precedent mismatch and reasons.** The model sometimes cites a ruling that does not match the candidate code. Compare cited ruling codes against the retrieved rulings and drop or flag mismatches, and add a one- or two-sentence reason per candidate code, shown in the expanded row and included in the CSV export so each row is audit-ready.

   From a user test on two metal-working coolants:

   - **Retrieval.** When all 5 nearest rulings fall in chapters unrelated to the model's candidates, search again restricted to the candidates' headings, and rewrite the description into customs wording before embedding. "Coolant" currently pulls rulings on cooling machinery (headings 8419, 8414, 8424, 7309).
   - **No relevant rulings.** When no relevant ruling is found, show "no relevant rulings found" instead of "0 of 5 agree".
   - **Subheading consistency check.** A description that says "without mineral oil" must not get a subheading defined as containing petroleum oils (3403.19 was given at 95 % instead of 3403.99), and the confidence must drop when the check fails.
   - **Subdivision by use.** When the description names the use, rank the matching TARIC subdivision first, e.g. 2710 19 91 metal-working compounds for a coolant with more than 70 % mineral oil.
   - **Index all chapters.** The EBTI store currently covers only twelve indexed chapters, so goods in other chapters (e.g. 27 and 34 for metal-working coolants and lubricants) have no rulings at all. `refresh_ebti` and the loader index rulings from every chapter, with the chapter list as a setting whose default is all; the demo store keeps `CARGOLINT_EBTI_RULINGS=5000`.
   - **Chapter-filtered retrieval.** Search the nearest rulings only within the chapters of the model's HS-6 candidates, so a coolant (2710, 3403) never matches cooling machinery in chapter 84.
   - **Unindexed chapters.** Until all chapters are indexed, when a candidate's chapter is not indexed, show "no rulings indexed for chapter NN" instead of "0 of 5 agree".

3. **Line-specific shipper questions.** Shipper questions must be specific to the line, not generic. If the material is already given, ask for what is missing, e.g. for a coolant the intended use and whether mineral oil is the basic constituent.

4. **015 Input guardrails.** Cap file size at about 2 MB and lines at about 200 per check, add a cheap no-model relevance check that stops files that do not look like an invoice or packing list, count a daily line budget across all inputs (file upload, single-line check, re-checks) with a "demo limit reached" message, and add a short cooldown between checks per session.

   **Milestone after 013-015:** remove the password and open the demo link publicly.

5. **UI language switch EN / DE / 中文.** Let the clerk switch the screen language, needed for Chinese-owned forwarders in Hamburg as the first target customers.

6. **One text input for one or many lines.** The "Check a single line" tab becomes one box that accepts either a single goods description or a free-text message from a shipper (Chinese, English or mixed, e.g. "two coolants, codes 2710199900 and 3403990000, one with more than 70% mineral oil, one without mineral base oil"). A cheap rule decides first: short text with no list markers, no "one ... one ..." pattern and at most one code is treated as one line with no extra model call; otherwise one model call splits it into goods lines (description, material, use, quantity, shipper's stated code). All resulting lines go straight into the existing result list and are checked as usual, with no confirmation table. A wrong split is fixed with the existing edit-description and re-check. Add one small control: delete a line. If the shipper stated a code, compare its first six digits with the suggested HS-6 and show "matches" or "differs, please check".

7. **TARIC subdivision descriptions.** Show the text of the 8- and 10-digit subdivisions, not only the code.

8. **Multi-file upload.** Check the invoice and packing list of one shipment in a single check, with a file column.

9. **Eval-set fixes.** Review and correct mislabelled lines in `tests/eval`. Add six lines from the user test on two metal-working coolants, with their expected results:

   - `冷却液 矿物油含量大于70%` → 2710.19
   - `没有矿物基础油的冷却液` → ask shipper for the intended use (3820.00 if engine coolant, 3403.99 if metal-working)
   - `金属加工用的冷却液，不含矿物油` → 3403.99
   - `coolant without mineral base oil, for metal working` → 3403.99
   - `金属加工冷却液，矿物油含量大于70% / Metal-working coolant, petroleum mineral oil content more than 70% by weight` → 2710.19 (CN 2710 19 91)
   - `金属加工冷却液，不含矿物基础油 / Metal-working coolant, without mineral base oil` → 3403.99

10. **Admin override slider.** Expose the accept/review confidence threshold as an admin slider.

11. **Shipper memory.** Remember a shipper's earlier answers and reuse them.

12. **stderr logging for the cloud demo.**

13. **Paid hosting on an EU server.** Hetzner with Docker and Caddy and an EU model endpoint, checking OpenRouter data privacy first.

14. **Constitution wording.** The governance paragraph still names feature 005 wireframes; wording-only amendment.
