# Backlog

Future work, in priority order. Each entry is a short sketch, not a spec; run it through Spec Kit when it is picked up.

1. **013 Knowledge base refresh.** EBTI rulings and TARIC data are frozen in demo-store-v1. Add a script that downloads current EBTI and TARIC data, rebuilds the vector store, publishes a new release, and shows the snapshot date in the app with a warning when it is older than 30 days.

2. **014 Precedent mismatch and reasons.** The model sometimes cites a ruling that does not match the candidate code. Compare cited ruling codes against the retrieved rulings and drop or flag mismatches, and add a one- or two-sentence reason per candidate code, shown in the expanded row and included in the CSV export so each row is audit-ready.

3. **015 Input guardrails.** Cap file size at about 2 MB and lines at about 200 per check, add a cheap no-model relevance check that stops files that do not look like an invoice or packing list, count a daily line budget across all inputs (file upload, single-line check, re-checks) with a "demo limit reached" message, and add a short cooldown between checks per session.

   **Milestone after 013-015:** remove the password and open the demo link publicly.

4. **UI language switch EN / DE / 中文.** Let the clerk switch the screen language, needed for Chinese-owned forwarders in Hamburg as the first target customers.

5. **TARIC subdivision descriptions.** Show the text of the 8- and 10-digit subdivisions, not only the code.

6. **Multi-file upload.** Check the invoice and packing list of one shipment in a single check, with a file column.

7. **Shipper code hint.** If a line carries a Chinese 10-digit customs code, use its first six digits as a strong HS-6 hint.

8. **Eval-set fixes.** Review and correct mislabelled lines in `tests/eval`.

9. **Admin override slider.** Expose the accept/review confidence threshold as an admin slider.

10. **Shipper memory.** Remember a shipper's earlier answers and reuse them.

11. **stderr logging for the cloud demo.**

12. **Paid hosting on an EU server.** Hetzner with Docker and Caddy and an EU model endpoint, checking OpenRouter data privacy first.

13. **Constitution wording.** The governance paragraph still names feature 005 wireframes; wording-only amendment.
