# Automatic Upstream Sync Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `aiograpi` detect newer stable `instagrapi` GitHub Releases every day and create exactly one durable sync-triage issue per release without adding cross-repository secrets.

**Architecture:** Move tracker behavior out of inline workflow YAML into one strict Bash script that uses `gh` for GitHub operations and `python3` only for baseline extraction, version ordering, and exact JSON matching. Exercise that real script through a fake `gh` executable, then reduce the workflow to triggers, permissions, canonical checkout, concurrency, and environment wiring.

**Tech Stack:** GitHub Actions YAML, Bash 3.2-compatible shell, Python 3.10+, pytest, PyYAML, GitHub CLI.

---

## File Map

- Create `scripts/upstream_sync_tracker.sh`: resolve event inputs, validate and order versions, query exact issues, and create the tracker issue.
- Modify `tests/regression/test_upstream_sync.py`: retain baseline/doc checks and add fake-CLI behavioral coverage plus structural workflow assertions.
- Modify `.github/workflows/upstream-sync.yml`: add cron, queued concurrency, canonical checkout, timeout, and call the tested script.
- Modify `docs/upstream-sync.md`: replace the future-work note with the actual automation contract and schedule limitations.
- Remove the tracked `docs/superpowers/specs/...` and `docs/superpowers/plans/...` artifacts from the public branch after execution; they are intentionally gitignored and are only local workflow inputs.

### Task 1: Resolve and compare upstream versions

**Files:**
- Create: `scripts/upstream_sync_tracker.sh`
- Modify: `tests/regression/test_upstream_sync.py`

- [ ] **Step 1: Add the fake `gh` harness and failing version-decision tests**

Add these imports, constants, helpers, and tests to `tests/regression/test_upstream_sync.py` while retaining its two existing baseline/documentation tests:

```python
import json
import os
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import aiograpi
import pytest


ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "scripts" / "upstream_sync_tracker.sh"


def _tracker_context(tmp_path, baseline="2.18.18"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    gh = fake_bin / "gh"
    gh.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            log = Path(os.environ["GH_CALL_LOG"])
            with log.open("a") as handle:
                handle.write(json.dumps(args) + "\\n")

            if args[:2] == ["api", "repos/subzeroid/instagrapi/releases/latest"]:
                if os.environ.get("GH_API_FAIL") == "1":
                    raise SystemExit(1)
                print(os.environ.get("GH_LATEST_TAG", "2.18.18"))
            elif args[:2] == ["issue", "list"]:
                if os.environ.get("GH_ISSUE_LIST_FAIL") == "1":
                    raise SystemExit(1)
                print(os.environ.get("GH_ISSUES", "[]"))
            elif args[:2] == ["issue", "create"]:
                if os.environ.get("GH_ISSUE_CREATE_FAIL") == "1":
                    raise SystemExit(1)
                body_file = Path(args[args.index("--body-file") + 1])
                Path(os.environ["GH_BODY_CAPTURE"]).write_text(body_file.read_text())
                print("https://github.com/subzeroid/aiograpi/issues/999")
            else:
                print(f"unexpected gh arguments: {args}", file=sys.stderr)
                raise SystemExit(2)
            """
        )
    )
    gh.chmod(0o755)

    baseline_file = tmp_path / "__init__.py"
    baseline_file.write_text(f'__upstream_instagrapi_version__ = "{baseline}"\n')
    call_log = tmp_path / "gh-calls.jsonl"
    body_capture = tmp_path / "issue-body.md"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
            "BASELINE_FILE": str(baseline_file),
            "GITHUB_REPOSITORY": "subzeroid/aiograpi",
            "GH_CALL_LOG": str(call_log),
            "GH_BODY_CAPTURE": str(body_capture),
            "GH_LATEST_TAG": "2.18.18",
            "GH_ISSUES": "[]",
        }
    )
    return SimpleNamespace(env=env, call_log=call_log, body_capture=body_capture)


def _run_tracker(context, event_name, workflow_tag="", dispatch_tag="", **env_overrides):
    env = context.env.copy()
    env.update(
        {
            "EVENT_NAME": event_name,
            "WORKFLOW_TAG": workflow_tag,
            "DISPATCH_TAG": dispatch_tag,
        }
    )
    env.update(env_overrides)
    return subprocess.run(
        [str(TRACKER)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _gh_calls(context):
    if not context.call_log.exists():
        return []
    return [json.loads(line) for line in context.call_log.read_text().splitlines()]


def test_scheduled_tracker_reads_latest_release_and_stops_at_current_baseline(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "schedule")

    assert result.returncode == 0
    assert "No upstream sync needed: 2.18.18 <= 2.18.18" in result.stdout
    assert _gh_calls(context) == [
        ["api", "repos/subzeroid/instagrapi/releases/latest", "--jq", ".tag_name"]
    ]


def test_explicit_older_target_stops_before_github_issue_calls(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "workflow_dispatch", workflow_tag="2.18.17")

    assert result.returncode == 0
    assert "No upstream sync needed: 2.18.17 <= 2.18.18" in result.stdout
    assert _gh_calls(context) == []


@pytest.mark.parametrize("target_tag", ["", "v2.18.19", "2.18", "2.18.19-rc1"])
def test_invalid_explicit_target_fails_before_github_calls(tmp_path, target_tag):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "workflow_dispatch", workflow_tag=target_tag)

    assert result.returncode == 1
    assert "Invalid instagrapi target tag" in result.stderr
    assert _gh_calls(context) == []


def test_invalid_baseline_fails_before_issue_calls(tmp_path):
    context = _tracker_context(tmp_path, baseline="not-a-version")

    result = _run_tracker(context, "workflow_dispatch", workflow_tag="2.18.19")

    assert result.returncode == 1
    assert "Invalid aiograpi upstream baseline" in result.stderr
    assert _gh_calls(context) == []


def test_scheduled_release_api_failure_is_visible_and_does_not_create_issue(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "schedule", GH_API_FAIL="1")

    assert result.returncode != 0
    assert _gh_calls(context) == [
        ["api", "repos/subzeroid/instagrapi/releases/latest", "--jq", ".tag_name"]
    ]


def test_scheduled_malformed_release_tag_fails_after_api_lookup(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "schedule", GH_LATEST_TAG="null")

    assert result.returncode == 1
    assert "Invalid instagrapi target tag" in result.stderr
    assert _gh_calls(context) == [
        ["api", "repos/subzeroid/instagrapi/releases/latest", "--jq", ".tag_name"]
    ]
```

- [ ] **Step 2: Run the new tests and confirm the red state**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py -k "scheduled_tracker or explicit_older or invalid or release_api"
```

Expected: failures because `scripts/upstream_sync_tracker.sh` does not exist.

- [ ] **Step 3: Implement event resolution, validation, and version ordering**

Create `scripts/upstream_sync_tracker.sh` with this initial implementation:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE_FILE="${BASELINE_FILE:-$ROOT/aiograpi/__init__.py}"
EVENT_NAME="${EVENT_NAME:-}"
WORKFLOW_TAG="${WORKFLOW_TAG:-}"
DISPATCH_TAG="${DISPATCH_TAG:-}"
TARGET_REPOSITORY="${GITHUB_REPOSITORY:-}"
UPSTREAM_REPOSITORY="subzeroid/instagrapi"
VERSION_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+$'

case "$EVENT_NAME" in
  schedule)
    TARGET_TAG="$(gh api "repos/$UPSTREAM_REPOSITORY/releases/latest" --jq .tag_name)"
    ;;
  workflow_dispatch)
    TARGET_TAG="$WORKFLOW_TAG"
    ;;
  repository_dispatch)
    TARGET_TAG="$DISPATCH_TAG"
    ;;
  *)
    echo "::error::Unsupported upstream sync event: ${EVENT_NAME:-missing}" >&2
    exit 1
    ;;
esac

if [[ ! "$TARGET_TAG" =~ $VERSION_PATTERN ]]; then
  echo "::error::Invalid instagrapi target tag: ${TARGET_TAG:-missing}; expected X.Y.Z" >&2
  exit 1
fi

CURRENT_TAG="$(python3 - "$BASELINE_FILE" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
match = re.search(
    r'^__upstream_instagrapi_version__\s*=\s*"([^"]+)"\s*$',
    text,
    re.MULTILINE,
)
print(match.group(1) if match else "")
PY
)"

if [[ ! "$CURRENT_TAG" =~ $VERSION_PATTERN ]]; then
  echo "::error::Invalid aiograpi upstream baseline: ${CURRENT_TAG:-missing}; expected X.Y.Z" >&2
  exit 1
fi

VERSION_ORDER="$(python3 - "$CURRENT_TAG" "$TARGET_TAG" <<'PY'
import sys

current = tuple(map(int, sys.argv[1].split(".")))
target = tuple(map(int, sys.argv[2].split(".")))
print((target > current) - (target < current))
PY
)"

if [[ "$VERSION_ORDER" -le 0 ]]; then
  echo "No upstream sync needed: $TARGET_TAG <= $CURRENT_TAG"
  exit 0
fi

echo "New upstream release detected: $CURRENT_TAG -> $TARGET_TAG"
```

Then make it executable:

```bash
chmod +x scripts/upstream_sync_tracker.sh
```

- [ ] **Step 4: Run the targeted tests and confirm green**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py -k "scheduled_tracker or explicit_older or invalid or release_api"
```

Expected: `9 passed` because the malformed explicit input test has four cases.

- [ ] **Step 5: Commit the version-decision unit**

```bash
git add scripts/upstream_sync_tracker.sh tests/regression/test_upstream_sync.py
git commit -m "feat: detect newer upstream releases"
```

### Task 2: Deduplicate and create sync issues

**Files:**
- Modify: `scripts/upstream_sync_tracker.sh`
- Modify: `tests/regression/test_upstream_sync.py`

- [ ] **Step 1: Add failing issue lifecycle tests**

Append these tests to `tests/regression/test_upstream_sync.py`:

```python
ISSUE_LIST_ARGS = [
    "issue",
    "list",
    "--repo",
    "subzeroid/aiograpi",
    "--state",
    "all",
    "--limit",
    "1000",
    "--json",
    "number,title,url,state",
]


def test_issue_list_failure_is_visible_and_does_not_create_issue(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(
        context,
        "workflow_dispatch",
        workflow_tag="2.18.19",
        GH_ISSUE_LIST_FAIL="1",
    )

    assert result.returncode != 0
    assert _gh_calls(context) == [ISSUE_LIST_ARGS]
    assert not context.body_capture.exists()


def test_exact_issue_in_any_state_suppresses_duplicate_creation(tmp_path):
    for state in ("OPEN", "CLOSED"):
        context = _tracker_context(tmp_path / state.lower())
        issue_url = "https://github.com/subzeroid/aiograpi/issues/500"
        issues = json.dumps(
            [
                {
                    "number": 500,
                    "title": "Sync aiograpi with instagrapi 2.18.19",
                    "url": issue_url,
                    "state": state,
                }
            ]
        )

        result = _run_tracker(
            context,
            "workflow_dispatch",
            workflow_tag="2.18.19",
            GH_ISSUES=issues,
        )

        assert result.returncode == 0
        assert issue_url in result.stdout + result.stderr
        assert _gh_calls(context) == [ISSUE_LIST_ARGS]
        assert not context.body_capture.exists()
        if state == "CLOSED":
            assert "::warning::" in result.stderr


def test_near_match_titles_do_not_suppress_issue_creation(tmp_path):
    context = _tracker_context(tmp_path)
    issues = json.dumps(
        [
            {
                "number": 1,
                "title": "Sync aiograpi with instagrapi 2.18.1",
                "url": "https://github.com/subzeroid/aiograpi/issues/1",
                "state": "OPEN",
            },
            {
                "number": 2,
                "title": "Sync aiograpi with instagrapi 2.18.190",
                "url": "https://github.com/subzeroid/aiograpi/issues/2",
                "state": "CLOSED",
            },
            {
                "number": 3,
                "title": "Sync aiograpi with instagrapi 2.18.19-rc1",
                "url": "https://github.com/subzeroid/aiograpi/issues/3",
                "state": "OPEN",
            },
        ]
    )

    result = _run_tracker(
        context,
        "workflow_dispatch",
        workflow_tag="2.18.19",
        GH_ISSUES=issues,
    )

    assert result.returncode == 0
    calls = _gh_calls(context)
    assert calls[0] == ISSUE_LIST_ARGS
    assert calls[1][0:4] == ["issue", "create", "--repo", "subzeroid/aiograpi"]
    assert calls[1][4:6] == ["--title", "Sync aiograpi with instagrapi 2.18.19"]
    assert calls[1][6] == "--body-file"
    body = context.body_capture.read_text()
    assert "Current aiograpi baseline: 2.18.18" in body
    assert "Target instagrapi tag: 2.18.19" in body
    assert "compare/2.18.18...2.18.19" in body


def test_issue_create_failure_is_visible(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(
        context,
        "repository_dispatch",
        dispatch_tag="2.18.19",
        GH_ISSUE_CREATE_FAIL="1",
    )

    assert result.returncode != 0
    assert [call[:2] for call in _gh_calls(context)] == [
        ["issue", "list"],
        ["issue", "create"],
    ]
```

- [ ] **Step 2: Run the lifecycle tests and confirm the red state**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py -k "issue_list_failure or exact_issue or near_match or issue_create_failure"
```

Expected: failures because the initial script stops after detecting a newer target and never lists or creates issues.

- [ ] **Step 3: Implement exact all-state deduplication and issue creation**

Replace the final `echo "New upstream release detected..."` line in `scripts/upstream_sync_tracker.sh` with:

```bash
if [[ -z "$TARGET_REPOSITORY" ]]; then
  echo "::error::GITHUB_REPOSITORY is required" >&2
  exit 1
fi

ISSUE_TITLE="Sync aiograpi with instagrapi $TARGET_TAG"
ISSUES_FILE="$(mktemp)"
BODY_FILE=""

cleanup() {
  rm -f "$ISSUES_FILE"
  if [[ -n "$BODY_FILE" ]]; then
    rm -f "$BODY_FILE"
  fi
}
trap cleanup EXIT

gh issue list \
  --repo "$TARGET_REPOSITORY" \
  --state all \
  --limit 1000 \
  --json number,title,url,state > "$ISSUES_FILE"

EXISTING_ISSUE="$(python3 - "$ISSUES_FILE" "$ISSUE_TITLE" <<'PY'
import json
import sys
from pathlib import Path

issues = json.loads(Path(sys.argv[1]).read_text())
title = sys.argv[2]
for issue in issues:
    if issue.get("title") == title:
        print(f"{issue.get('state', '')}\t{issue.get('url', '')}")
        break
PY
)"

if [[ -n "$EXISTING_ISSUE" ]]; then
  IFS=$'\t' read -r EXISTING_STATE EXISTING_URL <<< "$EXISTING_ISSUE"
  if [[ "$EXISTING_STATE" == "CLOSED" ]]; then
    echo "::warning::Upstream sync issue is already closed while the baseline is behind: $EXISTING_URL" >&2
  else
    echo "Upstream sync issue already exists: $EXISTING_URL"
  fi
  exit 0
fi

BODY_FILE="$(mktemp)"
{
  printf '%s\n\n' "A new instagrapi release needs aiograpi triage."
  printf 'Current aiograpi baseline: %s\n' "$CURRENT_TAG"
  printf 'Target instagrapi tag: %s\n' "$TARGET_TAG"
  printf 'Compare: https://github.com/subzeroid/instagrapi/compare/%s...%s\n\n' "$CURRENT_TAG" "$TARGET_TAG"
  printf '%s\n' "Checklist:"
  printf '%s\n' "- [ ] Review instagrapi release notes and changed files."
  printf '%s\n' "- [ ] Decide which changes are async-portable."
  printf '%s\n' "- [ ] Port features/fixes with regression tests."
  printf '%s\n' "- [ ] Update docs and aiograpi upstream baseline."
  printf '%s\n' "- [ ] Run local checks and CI."
  printf '%s\n' "- [ ] Publish an aiograpi release or record why no release is needed."
} > "$BODY_FILE"

gh issue create \
  --repo "$TARGET_REPOSITORY" \
  --title "$ISSUE_TITLE" \
  --body-file "$BODY_FILE"
```

- [ ] **Step 4: Run all tracker behavior tests and confirm green**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py
```

Expected: all tests in the module pass.

- [ ] **Step 5: Commit the issue lifecycle unit**

```bash
git add scripts/upstream_sync_tracker.sh tests/regression/test_upstream_sync.py
git commit -m "feat: deduplicate upstream sync issues"
```

### Task 3: Wire the tested script into GitHub Actions

**Files:**
- Modify: `.github/workflows/upstream-sync.yml`
- Modify: `tests/regression/test_upstream_sync.py`

- [ ] **Step 1: Add a failing structural workflow test**

Add `import yaml`, `WORKFLOW = ROOT / ".github" / "workflows" / "upstream-sync.yml"`, and this test to `tests/regression/test_upstream_sync.py`:

```python
def test_upstream_sync_workflow_is_scheduled_serialized_and_minimally_privileged():
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)

    assert workflow["on"]["schedule"] == [{"cron": "17 6 * * *"}]
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["on"]["repository_dispatch"]["types"] == ["instagrapi_release"]
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}
    assert workflow["concurrency"] == {
        "group": "upstream-sync-tracker",
        "queue": "max",
        "cancel-in-progress": "false",
    }

    job = workflow["jobs"]["create-sync-issue"]
    assert job["timeout-minutes"] == "10"
    checkout, tracker = job["steps"]
    assert checkout["uses"] == "actions/checkout@v7"
    assert checkout["with"] == {
        "ref": "${{ github.event.repository.default_branch }}",
        "persist-credentials": "false",
    }
    assert tracker["run"] == "scripts/upstream_sync_tracker.sh"
    assert tracker["env"] == {
        "GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
        "EVENT_NAME": "${{ github.event_name }}",
        "WORKFLOW_TAG": "${{ github.event.inputs.instagrapi_tag }}",
        "DISPATCH_TAG": "${{ github.event.client_payload.tag }}",
    }
    assert all("${{" not in step.get("run", "") for step in job["steps"])
```

- [ ] **Step 2: Run the structural test and confirm the red state**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py::test_upstream_sync_workflow_is_scheduled_serialized_and_minimally_privileged
```

Expected: failure because the current workflow has no schedule or concurrency and still contains the inline script.

- [ ] **Step 3: Replace the inline workflow with the scheduled wrapper**

Replace `.github/workflows/upstream-sync.yml` with:

```yaml
name: Upstream Sync Tracker

on:
  schedule:
    - cron: "17 6 * * *"
  workflow_dispatch:
    inputs:
      instagrapi_tag:
        description: "instagrapi tag to sync through, for example 2.18.19"
        required: true
        type: string
  repository_dispatch:
    types:
      - instagrapi_release

concurrency:
  group: upstream-sync-tracker
  queue: max
  cancel-in-progress: false

permissions:
  contents: read
  issues: write

jobs:
  create-sync-issue:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Check out canonical baseline
        uses: actions/checkout@v7
        with:
          ref: ${{ github.event.repository.default_branch }}
          persist-credentials: false

      - name: Create upstream sync issue when needed
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          EVENT_NAME: ${{ github.event_name }}
          WORKFLOW_TAG: ${{ github.event.inputs.instagrapi_tag }}
          DISPATCH_TAG: ${{ github.event.client_payload.tag }}
        run: scripts/upstream_sync_tracker.sh
```

- [ ] **Step 4: Run workflow checks and confirm green**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py
.venv/bin/pre-commit run check-yaml --files .github/workflows/upstream-sync.yml
```

Expected: all module tests pass and `check-yaml` reports `Passed`.

- [ ] **Step 5: Commit the workflow unit**

```bash
git add .github/workflows/upstream-sync.yml tests/regression/test_upstream_sync.py
git commit -m "ci: schedule upstream sync tracking"
```

### Task 4: Document the operational contract

**Files:**
- Modify: `docs/upstream-sync.md:55-64`

- [ ] **Step 1: Replace the future-automation section**

Replace `## Future automation` and its body with:

```markdown
## Automated release tracking

The `Upstream Sync Tracker` workflow checks GitHub's latest stable `instagrapi`
release every day at 06:17 UTC. It compares that tag with
`__upstream_instagrapi_version__` and creates one durable sync issue when the
upstream version is newer. Existing issues are matched by exact title across open
and closed states, so a closed or superseded tracker is not recreated daily.

Maintainers can also run the workflow with an explicit tag through
`workflow_dispatch` or send the existing `instagrapi_release`
`repository_dispatch` event. All modes record:

- previous `instagrapi` baseline;
- new `instagrapi` tag;
- compare URL;
- checklist of changed files and release-note items.

GitHub schedules are best-effort. They run from the default branch, can be delayed
or dropped during high Actions load, and are disabled for public repositories
after 60 days without repository activity. Manual dispatch remains available when
scheduled execution is delayed or disabled.
```

- [ ] **Step 2: Run documentation and regression checks**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py
.venv/bin/mkdocs build --strict
```

Expected: the module passes and MkDocs exits `0` without warnings.

- [ ] **Step 3: Commit the documentation unit**

```bash
git add docs/upstream-sync.md
git commit -m "docs: explain automatic upstream tracking"
```

### Task 5: Verify the complete change and prepare the public diff

**Files:**
- Delete from tracked public diff: `docs/superpowers/specs/2026-08-26-automatic-upstream-sync-tracker-design.md`
- Delete from tracked public diff: `docs/superpowers/plans/2026-08-26-automatic-upstream-sync-tracker.md`

- [ ] **Step 1: Run focused static and behavioral verification**

Run:

```bash
bash -n scripts/upstream_sync_tracker.sh
.venv/bin/python -m pytest -q tests/regression/test_upstream_sync.py
.venv/bin/ruff check tests/regression/test_upstream_sync.py
.venv/bin/ruff format --check tests/regression/test_upstream_sync.py
.venv/bin/pre-commit run --files \
  scripts/upstream_sync_tracker.sh \
  tests/regression/test_upstream_sync.py \
  .github/workflows/upstream-sync.yml \
  docs/upstream-sync.md
```

Expected: shell parse succeeds, all focused tests pass, Ruff passes, and every pre-commit hook passes or reports no applicable files.

- [ ] **Step 2: Run the full regression and strict documentation gates**

Run:

```bash
.venv/bin/python -m pytest -q tests/regression
.venv/bin/mkdocs build --strict
```

Expected: the full regression suite passes with only its existing skips, and MkDocs exits `0` without warnings.

- [ ] **Step 3: Remove local planning artifacts from the public branch diff**

Delete only these two tracked files with the patch tool:

```text
docs/superpowers/specs/2026-08-26-automatic-upstream-sync-tracker-design.md
docs/superpowers/plans/2026-08-26-automatic-upstream-sync-tracker.md
```

Then commit their removal:

```bash
git add -u docs/superpowers
git commit -m "chore: omit local planning artifacts"
```

The files are intentionally covered by `.gitignore`; their add/delete commits cancel out of the PR diff.

- [ ] **Step 4: Inspect the exact public diff and secret surface**

Run:

```bash
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- \
  .github/workflows/upstream-sync.yml \
  scripts/upstream_sync_tracker.sh \
  tests/regression/test_upstream_sync.py \
  docs/upstream-sync.md
rg -n -i "(password|passwd|secret|token|api[_-]?key|sessionid|authorization|proxy)" \
  .github/workflows/upstream-sync.yml \
  scripts/upstream_sync_tracker.sh \
  tests/regression/test_upstream_sync.py \
  docs/upstream-sync.md
```

Expected: no whitespace errors; only the four intended public files differ; secret scan finds only documented `GITHUB_TOKEN` references and test variable names, never credential values.

- [ ] **Step 5: Request independent code review and address all blocking or important findings**

Provide reviewers with `origin/main` as the base, the final `HEAD`, this implementation plan, and the four-file public diff. Re-run the focused verification after any accepted review fix.

- [ ] **Step 6: Push GitHub and Codeberg branches and open the PR without merging**

Use the repository ship workflow to push `chore/upstream-sync-schedule` to both remotes and create a GitHub PR targeting `main`. The PR body must state that the workflow uses only `GITHUB_TOKEN`, creates no secrets, and was verified with fake-CLI failure paths, full regression tests, and strict docs.
