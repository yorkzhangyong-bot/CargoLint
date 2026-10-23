# Specification Quality Checklist: CN-8 and TARIC-10 Classification in the Agent and the UI

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Iteration 1 (2026-10-23): 5 user stories, 23 functional requirements, 7 success criteria; three [NEEDS CLARIFICATION] markers, all put to the author:
  - User Story 2, scenario 6: whether a pending TARIC-10 confirmation makes the line "needs action";
  - User Story 3, scenario 3 (and FR-016): the EZT-online link, since the site has no stable per-code links;
  - FR-011: whether trade-defence types other than 551–554 also require confirmation.
- Iteration 2 (2026-10-23): the author answered Q1 B, Q2 C and Q3 B. The answers are recorded under Clarifications and applied:
  - Q1, B: a pending TARIC-10 confirmation leaves the line's HS-6 route as it is and shows a "TARIC-10 to confirm" marker and count (User Story 2 scenario 6, FR-009, FR-011, Assumptions).
  - Q2, C: two links, EZT-online's start page with the code and origin for copying, and the EU TARIC consultation page for the code and origin (User Story 3 scenario 3, FR-016); planning verifies the EU link format.
  - Q3, B: types 551 to 555 and 570 require confirmation, and 561, 564 and 565 are shown but do not force it. This applies to FR-011 and to the auto-complete condition in FR-008, User Story 2 scenarios 1 and 5, and SC-005; FR-014 lists the trade-defence group's types.
  All 16 items now pass.
- Facts checked against the code and data on 2026-10-23:
  - `CODE_PATTERN` is `^\d{4}\.\d{2}$`;
  - `Shipment.origin` is the route origin parsed from the invoice and shown in the review header, so the TARIC origin is a separate field;
  - EBTI rulings carry a `cn_code` of up to 10 digits;
  - 7318 15 58 10 for China carries "39.6 % with anti-dumping/countervailing document D008; otherwise 86.5 %" and 1008's 763 and 775;
  - the last labelled-set run (2026-10-16) gave flags 20/20, top-1 10/12, top-3 12/12.
- Implementation names appear only in the author's Input line and in the "Design constraints set by the author" list in Assumptions. A Streamlit mention in Assumptions cites constitution Principle VI.
- Constitution dependency settled: v1.2.0 (2026-10-23) extends Principle I to CN-8, TARIC-10 and measures, adds the confirmation rule, the code formats and the CN-8 routing input, and lists seven tools. Assumptions record this.
