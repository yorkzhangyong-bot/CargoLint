# QA platform

CargoLint uses the [agentic QA platform](https://github.com/yorkzhangyong-bot/agentic-qa-platform): reusable GitHub
Actions workflows whose AI agents write Playwright browser tests from a spec, triage failing tests, repair selector
drift and report real bugs. The agents run on OpenCode with DeepSeek. Everything they produce comes back as a pull
request or an issue for review; they merge nothing.

## What runs when

| Workflow | Runs on | What it does |
|---|---|---|
| `.github/workflows/test-and-heal.yml` | every push to a pull request, every push to `main` | Runs the Playwright tests in `tests/e2e-browser` against the app started on the runner. No agent runs while they pass. When a test fails, the triage agent classifies each failure; selector drift goes to the healer, which opens an `auto-heal` pull request, and a real bug becomes an issue labelled `bug` and `agentic-qa`. |
| `.github/workflows/generate-tests.yml` | a manual run with `spec_path`, nothing else | The planner and generator agents turn the spec into tests, checked against the running app; the tests run once more and come back as an `auto-generate` pull request, a draft when they fail. |
| `.github/workflows/traceability.yml` | every pull request to `main`: opened, pushed to, reopened, or its description edited | No agent and no model: the spec check, or the tests-traceability check and the description rules ([Traceability](#traceability)). |

Both callers pin the platform to one commit of its `main`, so a push to the platform changes nothing here until the
pin is bumped ([Updating the platform](#updating-the-platform)).

## Required checks

The checks to require on `main`, as GitHub names them: `offline-suite` (`tests.yml`), `traceability`
(`traceability.yml`) and `browser-tests` (`test-and-heal.yml`). `browser-tests` is the check for the browser tests: a
job of CargoLint's own after the platform's, green only when the tests ran and passed. The platform's checks are no
substitute: `qa / Run playwright tests` stays green when a browser test fails, because the platform's "Run tests" step
has `continue-on-error` so that triage and healing can follow, and `qa / Triage`, `qa / Heal selector drift` and
`qa / Report defects` are skipped while the tests pass. The pull requests the platform opens (auto-heal, auto-generate)
start no workflow, as GitHub starts none for the workflow token's events: close and reopen such a pull request to run
its checks.

## Secrets

Two repository secrets, under Settings › Secrets and variables › Actions › Repository secrets (secrets of a GitHub
Environment never reach the platform's reusable workflows):

| Secret | What it is for |
|---|---|
| `DEEPSEEK_API_KEY` | The agents' model: OpenCode with the platform's default model, `deepseek/deepseek-flash`. A dedicated key with a low spending limit, because within an agent step it sits in the agent's environment. |
| `CI_APP_OPENROUTER_API_KEY` | CargoLint's own key in CI, separate from the demo's and the refresh workflow's. The callers pass it to the app as `OPENROUTER_API_KEY` inside the `APP_ENV` secret, which the platform loads only into the test runs and masks in the logs, never into an agent step. Never pass it as the platform's top-level `OPENROUTER_API_KEY` secret: that one goes to the OpenCode agents. The test runs execute the generated and healed tests, code an agent wrote, with this key in their environment, so such code can read and spend it: its credit limit at OpenRouter is the real cap. A test must never log its environment, because the JUnit report and the `test-results` artifact are public. |

Repository settings the platform needs: Settings › Actions › General › "Allow GitHub Actions to create and approve pull
requests" is on (the auto-heal and auto-generate pull requests). The default workflow permissions stay read-only; the
callers grant what their jobs need.

## The app in CI

The workflows start the app themselves (`app_start_command`): `uv` installs the locked dependencies (`uv.lock`, Python
3.13, as the cloud demo runs), then Streamlit listens on 127.0.0.1:8501 only (`--server.address 127.0.0.1`), which the
tests and agents reach as `http://localhost:8501` (`app_url`). The command is printed in the log, so it holds settings
only: the demo knowledge base, release `demo-store-v1`, with its checksum (`CARGOLINT_DEMO_STORE_URL`,
`CARGOLINT_DEMO_STORE_SHA256`), and the two telemetry switches. `app_ready_timeout` (600 s) covers the install.

A fresh runner has no `store/`, so the first page load downloads the 150 MB demo store and opens it, about half a
minute. `playwright.global-setup.ts` makes that load before the tests start and waits for it, up to five minutes; the
tests then load the page in a few seconds.

In a job that runs agents the platform starts the app twice: without `APP_ENV` for the agents, and with it for the test
run, so no agent can read the key from the app's process. The start command sets
`OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-ci-placeholder-not-a-key}"`: the test runs keep the key from `APP_ENV`, and
the agents' app gets a placeholder that is no key. The agents therefore explore the app without a model: the pages and
the knowledge base load, and a line check fails with 401 there ("check failed", routed to ask shipper). Only the
workflow's own test runs classify lines. The key's value never appears on a command line or in the log: the platform
prints the command as written, and bash expands the key into the app's environment only. Without the
`CI_APP_OPENROUTER_API_KEY` secret the test runs get the placeholder too (the platform warns about the empty `APP_ENV`
value), and a test that checks lines fails.

## Browser tests

- `tests/e2e-browser/` holds the Playwright tests (`*.spec.ts`). `playwright.config.ts` reads the base URL from
  `BASE_URL` or `APP_URL` (default `http://localhost:8501`), writes the JUnit report `results/junit.xml` that the
  platform reads, and has a `webServer` that reuses an app already listening there (`reuseExistingServer: true`) or
  starts `streamlit run app.py` when nothing does.
- `main-page.spec.ts` is the smoke test: the main page loads with its knowledge base (the header, the TARIC snapshot
  date, the two input tabs). It checks no line, so no model is called.
- The Node tooling is test-only: `package.json` pins `@playwright/test`, and the app needs none of it.

To run them locally, from the repository root, with `OPENROUTER_API_KEY` set, a knowledge base in `store/` and the
`.venv` active (the `webServer` runs `streamlit`):

```bash
npm ci
npx playwright install chromium
npx playwright test               # reuses the app on port 8501, or starts it
```

## Generating tests

Run "Generate tests" from the Actions tab with `spec_path`, a Spec Kit feature folder such as
`specs/014a-retrieval-evidence` or a single markdown file, or from the command line:

```bash
gh workflow run generate-tests.yml -f spec_path=specs/014a-retrieval-evidence
```

GitHub runs a workflow by hand only once it is on `main`. The tests come back as an `auto-generate` pull request into
the branch the run started from. They cite requirements as bare ids (`/** Covers FR-003 */`); add the feature marker of
[Traceability](#traceability) when you take them into a feature.

The platform template's other trigger, an issue labelled `ready-for-tests`, is left out: the platform reads the issue
when the job runs, so its raw text, hidden HTML comments and edits made after the label included, would become agent
input in a job that holds a write token and both keys. CargoLint's specs are Spec Kit folders, which `spec_path`
covers. The caller still grants `issues: read`, although it passes no issue and nothing reads one: the platform's
generate job declares that permission, and GitHub refuses to start a reusable workflow whose job asks for more than its
caller grants.

## Reviewing the platform's pull requests

The platform's anti-cheat check forbids changes to `src/` and its built-in paths (`.github/`, `*.config.*`,
`playwright.config.*`, `package*.json`, `.env*` and the like), but not to `app.py`, `agent/`, `tools/`, `rag/`, `ui/`,
`data/`, `scripts/`, `pyproject.toml`, `uv.lock` or `playwright.global-setup.ts`. OpenCode's own edits stay in
`tests/e2e-browser`, but test code it writes runs in the job and can change any file, and the pull request commits every
change. Until the platform offers a caller input for forbidden or allowed paths, check every `auto-heal` and
`auto-generate` pull request for files outside `tests/e2e-browser` before you merge it.

## Labels

| Label | Meaning |
|---|---|
| `ready-for-tests` | Not used by CargoLint: `generate-tests.yml` has no issue trigger ([Generating tests](#generating-tests)). |
| `auto-generate` | Set by the platform on a pull request of generated tests. |
| `auto-heal` | Set by the platform on a pull request of healed tests. A later heal for the same base branch updates the open one. |
| `bug`, `agentic-qa` | Set by the platform on the issue of a real bug; it finds the open issue for the same failure again by `agentic-qa`. |

## Cost

- While the browser tests pass, no agent runs: a pull request costs runner minutes only (the install, the demo store
  download, Chromium).
- Each push to a pull request whose browser tests fail runs the triage agent, then the healer and the defect reporter,
  on DeepSeek. The budget options of the platform's template: heal pull requests only on request (the label-gated
  variant in the comments of `test-and-heal.yml`: `pull_request: types: [labeled]`, the job's `if:` and a
  `heal-tests` label), no defect issues (`report_defects: false`), and smaller turn budgets (`triage_max_turns` 15,
  `heal_max_turns` 40 and `defect_max_turns` 20 by default; `plan_max_turns` 20 and `generate_max_turns` 80 for
  generation; on OpenCode a turn is emulated as 30 s).
- A generate run costs a planner, a generator and a pull-request writer.
- The app's key is spent by tests that check lines: about $0.002 a line, from the end-to-end evaluation's $0.27 for 120
  lines. The smoke test checks none; a generated test that checks lines spends on every run of `test-and-heal.yml`.
- The spending limits on the two keys are the hard cap.

## Updating the platform

Both callers name the platform by a full commit SHA, with the date of that commit on the platform's `main` as a comment
(`@e07861991797b0b36ea95a3ce1bbf42c1c1e0227 # main 2026-11-16`); the platform's scripts, agents and settings come from
the same commit. `@main` would run whatever is pushed there next, with this repository's write token and both keys,
before anyone reviews it. Bump the pin deliberately, in a pull request of its own:

1. Read what changed since the pinned commit, above all in `.github/workflows/`, `scripts/`, `agents/` and `settings/`:
   `gh api repos/yorkzhangyong-bot/agentic-qa-platform/compare/<pinned SHA>...main --jq '.files[].filename'`, then the
   diffs themselves.
2. Take the new commit and its date:
   `gh api repos/yorkzhangyong-bot/agentic-qa-platform/commits/main --jq '.sha + " " + .commit.committer.date'`.
3. Put the full SHA and the date into both `test-and-heal.yml` and `generate-tests.yml`
   (`tests/unit/test_qa_workflows.py` checks that the two pins are one full SHA), and merge only after the pull
   request's Test & heal run passes.

## Traceability

The `traceability` workflow (`.github/workflows/traceability.yml`) runs `scripts/check_traceability.py`, which uses
`scripts/check_spec.py` (unit tests in `tests/unit/test_check_spec.py` and `tests/unit/test_check_traceability.py`). It
runs on every pull request to `main`, and again when the description is edited, so adding a missing line clears a
failure without a push. The changed files decide a pull request's kind:

- **Spec-only**, when it changes none of `app.py`, `agent/`, `tools/`, `rag/`, `ui/`, `tests/`, `scripts/` and `data/`:
  the spec check of the branch's feature folder, `specs/<label>-*` (branch `014a-retrieval-evidence`: label `014a`).
  - It fails when `spec.md` defines an `FR-###` or `SC-###` more than once, or when an id in the folder's markdown
    files is malformed. Only `spec.md` defines (`- **FR-001**`): the same line in another file, such as a success
    criterion restated in `quickstart.md`, defines nothing. Gaps in the numbering are allowed, and ids in code spans
    are ignored.
  - Another feature's requirement written with its feature is no reference of this one: `002/FR-020` (or
    `002-FR-020`), "feature 002's FR-020", "(feature 002, FR-020)" and "feature 002 FR-020". Each id needs its own
    feature: in "feature 002's FR-014 and FR-018" only FR-014 counts as feature 002's.
  - Any other id that `spec.md` does not define is a warning, an annotation on the run, not a failure: another
    feature's requirement written without its feature ("its FR-018"), or a typo. The specs 003, 004 and 008 have such
    warnings and pass.
  - A branch without a feature label has nothing to check.
- **Implementation**, otherwise:
  - **Tests-traceability** for the branch's feature: every `FR-###` and `SC-###` that `specs/<label>-*/spec.md`
    defines is referenced by a test that names the feature, either as a scoped token `014a/FR-001` (or
    `014a-FR-001`) anywhere in a test (`tests/**/*.py`, `tests/e2e-browser/**/*.ts`), or as a bare `FR-001` in a
    test file with the module-level marker `FEATURE = "014a"` (`const FEATURE = '014a';` in TypeScript). A
    requirement no test can check (an evaluation result, a manual step, a setting) is justified in
    `specs/<label>-*/traceability.md` by a line `014a/FR-001: <reason>`. A branch without a feature label skips this
    check.
  - **Description rules**: a pull request that changes the app (`app.py`, `agent/`, `tools/`, `rag/`, `ui/`), on any
    branch, has a line `Spec-PR: #<n>` naming the merged spec pull request; one that changes a spec file as well has a
    line `spec-change: <reason>`.

Only the branch's own feature is checked, so the features before 014a, whose tests cite requirements without the
feature label, are not checked again.
