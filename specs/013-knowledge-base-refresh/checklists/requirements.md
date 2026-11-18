# Specification Quality Checklist: Knowledge Base Refresh

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-13
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

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
- The spec names files, commands and settings where the user's brief names them (the two scripts, the release names,
  the settings, the metadata file): they are the feature's interface, as in features 002 and 011, not implementation
  detail.
- Re-validated after `/speckit-clarify` (session 2026-11-13, four questions): the TARIC limit is 40 days on the
  snapshot date; the EBTI refresh reuses the previous store's vectors and embeds only new or changed rulings, with a
  manual full re-embed flag; the app resolves the newest release of each kind, with an optional pin; the store's size
  is the `CARGOLINT_EBTI_RULINGS` setting, 5,000 by default for the demo and `all` for every valid ruling in a
  production store. All items still pass.
- Re-validated after review round 1 (2026-11-13, 16 findings): the four clarifications stand; the spec now defines
  a complete release, the latest-release pointer the app reads instead of the rate-limited listing, the pin's
  fallback, a TARIC fetch failure that does not stop the app, the newest complete batch, `--force` and the work
  folder, the extended offline guard, the eval method of SC-003 and "at most two" in SC-007. All items still pass.
- Re-validated after review round 2 (2026-11-13, 8 findings): tests pass the loader a temporary store folder; the
  `current` block comes from a listing read right before publishing, the workflow's jobs run one after the other and
  the app falls back to the listing when every pointer-named release fails; `--full-embed` reaches the fakes; the
  work folder is checked after "nothing new"; exit 3 for a service failure after the build; `--force` deletes and
  recreates instead of patching assets. All items still pass.
- Re-validated after review round 3 and the owner's store-size change (2026-11-13): a nothing-new run still prunes and
  re-marks the latest release when needed; the TARIC batch folder is `rag.loader.TARIC_RAW_DIR` read at call time;
  the EBTI store size is the `CARGOLINT_EBTI_RULINGS` setting (5,000 by default; `all` for every valid ruling), with
  SC-002 covering both sizes and the size-agnostic SC-003. All items still pass.
- Re-validated after `/speckit-analyze` (2026-11-13, one HIGH and four MEDIUM findings, no constitution conflict): the
  release service gains the latest-release query and the listing's publish times, which FR-010's re-mark rule needs;
  a nothing-new run whose retention or re-marking fails exits 3; a pin must have the form `<kind>-YYYY-MM-DD` or the
  settings are refused at start; `--no-publish` still needs `gh` for a previous store that is a release; after a
  stale pointer the listing gives at most two untried releases. All items still pass.
