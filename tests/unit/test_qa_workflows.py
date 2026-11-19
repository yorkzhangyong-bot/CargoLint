"""The agentic QA workflows' security settings (docs/qa-platform.md; PR #8's security review): the platform pinned to
one full commit SHA in both callers, generation only by hand from a spec path, the app key only inside APP_ENV, the app
listening on 127.0.0.1 only, and the traceability check run again when a pull request's description is edited."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
PLATFORM = "yorkzhangyong-bot/agentic-qa-platform/.github/workflows/"
CALLERS = ["test-and-heal.yml", "generate-tests.yml"]


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def triggers(workflow: dict) -> dict:
    return workflow.get(True) or workflow.get("on")                   # YAML 1.1 reads the `on` key as True


def caller(name: str) -> dict:
    return next(iter(load(name)["jobs"].values()))


def test_both_callers_pin_the_platform_to_the_same_full_commit_sha_with_its_date():
    pins = set()
    for name in CALLERS:
        path, _, sha = caller(name)["uses"].partition("@")
        assert path == PLATFORM + name and re.fullmatch(r"[0-9a-f]{40}", sha), caller(name)["uses"]
        assert re.search(rf"@{sha} # main \d{{4}}-\d{{2}}-\d{{2}}$", (WORKFLOWS / name).read_text(encoding="utf-8"),
                         re.MULTILINE)
        pins.add(sha)
    assert len(pins) == 1


def test_tests_are_generated_only_by_hand_from_a_spec_path():
    workflow = load("generate-tests.yml")
    assert list(triggers(workflow)) == ["workflow_dispatch"]                # no issue trigger: no issue text as input
    assert triggers(workflow)["workflow_dispatch"]["inputs"]["spec_path"]["required"] is True
    job = caller("generate-tests.yml")
    assert "if" not in job and "issue_number" not in job["with"]
    assert job["with"]["spec_path"] == "${{ inputs.spec_path }}"
    # issues: read stays because the platform's generate job declares it; GitHub refuses to start a reusable workflow
    # whose job asks for more than its caller grants
    assert job["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "read"}
    heal = caller("test-and-heal.yml")
    assert heal["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "write"}


@pytest.mark.parametrize("name", CALLERS)
def test_the_app_key_reaches_only_app_env_and_the_app_listens_on_127_0_0_1(name):
    job = caller(name)
    assert job["with"]["engine"] == "opencode" and set(job["secrets"]) == {"DEEPSEEK_API_KEY", "APP_ENV"}
    assert job["secrets"]["APP_ENV"].strip() == "OPENROUTER_API_KEY=${{ secrets.CI_APP_OPENROUTER_API_KEY }}"
    command = job["with"]["app_start_command"]
    assert "${{" not in command and "secrets." not in command
    assert 'OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-ci-placeholder-not-a-key}"' in command
    assert "--server.address 127.0.0.1 --server.port 8501" in command
    assert job["with"]["app_url"] == "http://localhost:8501"


def test_traceability_runs_again_when_the_description_is_edited():
    workflow = load("traceability.yml")
    assert triggers(workflow)["pull_request"] == {"branches": ["main"],
                                                 "types": ["opened", "edited", "synchronize", "reopened"]}
    assert workflow["permissions"] == {"contents": "read"}
    step = workflow["jobs"]["traceability"]["steps"][-1]
    assert step["run"] == "python scripts/check_traceability.py"
    assert step["env"] == {"PR_BODY": "${{ github.event.pull_request.body }}"}
    assert list(load("tests.yml")["jobs"]) == ["offline-suite"]
