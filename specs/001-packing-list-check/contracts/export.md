# Contract: Results Export (CSV and JSON)

**Feature**: `001-packing-list-check` · **Spec**: FR-041, US4 · **Data model**: [../data-model.md](../data-model.md)

Both files are produced from `LineStore.export_rows()` — one row per line, current version only,
all lines regardless of route, ordered by `line_no`. File names:
`cargolint_<reference-or-shipment-id>_<YYYYMMDD-HHMM>.csv` / `.json`. CSV is UTF-8 with BOM
(so Excel opens Chinese text correctly), comma-separated, header row included.

## CSV columns (in this order)

| Column | Type | Source |
|---|---|---|
| `line_no` | int | Line |
| `text_zh` | str | current version |
| `text_en` | str | current version |
| `qty` | str | Line |
| `flag` | `ok \| vague \| stop_word` | Flag.kind |
| `flag_rule` | str | `firm:gift`, `ics2:parts`, `judgement`, empty when ok |
| `hs6_1`, `conf_1`, `hs6_2`, `conf_2`, `hs6_3`, `conf_3` | str, int | candidates (blank when fewer) |
| `precedent_1` | str | BTI reference of the top candidate's precedent, if any |
| `route` | `auto_accept \| accepted \| review \| ask_shipper` | effective route (`accepted` = clerk decision) |
| `route_set_by` | `routing_rule \| clerk` | |
| `decided_code` | str | blank unless auto-accepted or accepted |
| `decided_how` | `auto \| top \| other_candidate \| typed` | blank unless decided |
| `version_no` | int | |
| `last_change` | ISO-8601 datetime | current version `created_at` or decision `at`, whichever is later |
| `status` | `checked \| failed` | |
| `note` | str | error reason, contradiction note or truncation/unreadable marker |

## JSON

```json
{
  "shipment": {"id": "…", "reference": "HOL-2026-10-0472", "shipper": "Yiwu Hengfa Trading",
               "threshold": 85, "exported_at": "2026-10-14T13:05:00+02:00",
               "knowledge_base_updated": "2026-10-06", "usage": {"total_tokens": 18400, "cost_eur": 0.03}},
  "lines": [
    {
      "line_no": 1, "text_zh": "配件", "text_en": "Parts", "qty": "14 CTN",
      "flag": {"kind": "vague", "rule": "ics2:parts", "ask_for": ["material", "product_name", "use"]},
      "candidates": [{"code": "8452.90", "confidence": 31, "history_only": true, "precedent": "DE…"}],
      "route": "ask_shipper", "route_set_by": "routing_rule",
      "decided_code": null, "decided_how": null,
      "version_no": 1, "last_change": "2026-10-14T12:58:11+02:00", "status": "checked", "note": null
    }
  ]
}
```

JSON carries the same fields as the CSV plus the full candidate list (code, subheading text,
confidence, `history_only`, precedent reference) and the flag's `ask_for`. Neither file includes
the audit log, retrieval traces, reply texts or any shipper contact details (FR-046; audit export
is roadmap).
