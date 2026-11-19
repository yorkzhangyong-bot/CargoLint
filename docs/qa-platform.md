# QA platform

CargoLint uses the [agentic QA platform](https://github.com/yorkzhangyong-bot/agentic-qa-platform): reusable GitHub
Actions workflows whose AI agents write Playwright browser tests from a spec, triage failing tests, repair selector
drift and report real bugs. The agents run on OpenCode with DeepSeek. Everything they produce comes back as a pull
request or an issue for review; they merge nothing.

## What runs when

| Workflow | Runs on | What it does |
|---|---|---|
| `.github/workflows/test-and-heal.yml` | every push to a pull request, every push to `main` | Runs the Playwright tests in `tests/e2e-browser` against the app started on the runner. No agent runs while they pass. When a test fails, the triage agent classifies each failure; selector drift goes to the healer, which opens an `auto-heal` pull request, and a real bug becomes an issue labelled `bug` and `agentic-qa`. |
| `.github/workflows/generate-tests.yml` | a manual run with `spec_path`, or an issue labelled `ready-for-tests` | The planner and generator agents turn the spec into tests, checked against the running app; the tests run once more and come back as an `auto-generate` pull request, a draft when they fail. |
| `traceability` job in `.github/workflows/tests.yml` | every pull request to `main` | No agent and no model: the spec check, or the tests-traceability check and the description rules ([Traceability](#traceability)). |

Both callers take the platform's workflows at `@main`, so a change to the platform applies from its next run.

## Secrets

Two repository secrets, under Settings › Secrets and variables › Actions › Repository secrets (secrets of a GitHub
Environment never reach the platform's reusable workflows):

| Secret | What it is for |
|---|---|
| `DEEPSEEK_API_KEY` | The agents' model: OpenCode with the platform's default model, `deepseek/deepseek-flash`. A dedicated key with a low spending limit, because within an agent step it sits in the agent's environment. |
| `CI_APP_OPENROUTER_API_KEY` | CargoLint's own key in CI, separate from the demo's and the refresh workflow's. The callers pass it to the app as `OPENROUTER_API_KEY` inside the `APP_ENV` secret, which the platform loads only into the test runs and masks in the logs, never into an agent step. Never pass it as the platform's top-level `OPENROUTER_API_KEY` secret: that one goes to the OpenCode agents. Give it a low credit limit at OpenRouter. |

Repository settings the platform needs: Settings › Actions › General › "Allow GitHub Actions to create and approve pull
requests" is on (the auto-heal and auto-generate pull requests). The default workflow permissions stay read-only; the
callers grant what their jobs need.

## The app in CI

The workflows start the app themselves (`app_start_command`): `uv` installs the locked dependencies (`uv.lock`, Python
3.13, as the cloud demo runs), then Streamlit listens on `http://localhost:8501` (`app_url`). The command is printed in
the log, so it holds settings only: the demo knowledge base, release `demo-store-v1`, with its checksum
(`CARGOLINT_DEMO_STORE_URL`, `CARGOLINT_DEMO_STORE_SHA256`), and the two telemetry switches. `app_ready_timeout` (600 s)
covers the install.

A fresh runner has no `store/`, so the first page load downloads the 150 MB demo store and opens it, about half a
minute. `playwright.global-setup.ts` makes that load before the tests start and waits for it, up to five minutes; the
tests then load the page in a few seconds.

In a job that runs agents the platform starts the app twice: without `APP_ENV` for the agents, and with it for the test
run, so no agent can read the key from the app's process. The agents' app therefore has no `OPENROUTER_API_KEY` and
stops at "OPENROUTER_API_KEY is not set": the triage, healer and generator agents see that page, not the main page,
and say so. Only the workflow's own test runs reach the main page.

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

GitHub runs a workflow by hand only once it is on `main`. An issue labelled `ready-for-tests` works too: its title and
body become the spec. The tests come back as an `auto-generate` pull request into the branch the run started from.
They cite requirements as bare ids (`/** Covers FR-003 */`); add the feature marker of [Traceability](#traceability)
when you take them into a feature.

## Labels

| Label | Meaning |
|---|---|
| `ready-for-tests` | On an issue: generate tests from it. Only maintainers should apply it, because the issue text becomes agent input. |
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
- The app's key is spent only by tests that check lines: about $0.002 a line, from the end-to-end evaluation's $0.27
  for 120 lines. The smoke test checks none; a generated test that checks lines spends on every run of
  `test-and-heal.yml`.
- The spending limits on the two keys are the hard cap.

## Traceability

The `traceability` job runs `scripts/check_traceability.py`, which uses `scripts/check_spec.py` (unit tests in
`tests/unit/test_check_spec.py` and `tests/unit/test_check_traceability.py`). The changed files decide a pull
request's kind:

- **Spec-only**, when it changes none of `app.py`, `agent/`, `tools/`, `rag/`, `ui/`, `tests/`, `scripts/` and `data/`:
  the spec check of the branch's feature folder, `specs/<label>-*` (branch `014a-retrieval-evidence`: label `014a`).
  Across the folder's markdown files every `FR-###` and `SC-###` is well-formed, defined once (`- **FR-001**`), and
  none is referenced without a definition; ids in code spans are ignored. A branch without a feature label has
  nothing to check.
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
