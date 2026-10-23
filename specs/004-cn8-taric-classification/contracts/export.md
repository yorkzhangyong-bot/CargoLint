# Contract: export changes for CN-8 and TARIC-10

Changes feature 001's [export.md](../../001-packing-list-check/contracts/export.md). Every existing CSV column keeps
its position, name and value; every existing JSON key keeps its value (FR-021).

## CSV

Two columns are appended after `note`:

| Column | Value |
|---|---|
| `cn8` | the written CN-8 (by rule or by the clerk), eight digits without spaces. Empty while it is a suggestion or a question is open, and whenever `decided_code` is empty, for example after the clerk sends the line to review or to the shipper |
| `taric10` | the written TARIC-10 (auto-completed or confirmed by the clerk), ten digits. Empty while a confirmation is pending, when TARIC is not available or not loaded, and whenever `cn8` is empty |

## JSON

Each object in `lines` gains `"cn8"` and `"taric10"`, as a string or `null`, with the same values as the CSV columns.

## Note on clerk confirmations

A clerk confirmation on an auto-accepted line records a `Decision`. That line's `route` reads `accepted` and its
`route_set_by` reads `clerk`, because the clerk acted on it. Its `decided_code` and `decided_how` (`auto`) are
unchanged (research R-09).
