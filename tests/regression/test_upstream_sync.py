import json
import os
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import aiograpi

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "scripts" / "upstream_sync_tracker.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "upstream-sync.yml"

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


def _tracker_context(tmp_path, baseline="2.18.18"):
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True)
    baseline_file = tmp_path / "aiograpi" / "__init__.py"
    baseline_file.parent.mkdir(parents=True)
    baseline_file.write_text(f'__upstream_instagrapi_version__ = "{baseline}"\n')
    call_log = tmp_path / "gh-calls.jsonl"
    body_capture = tmp_path / "gh-body.txt"
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import shutil
            import sys

            argv = sys.argv[1:]
            with open(os.environ["GH_CALL_LOG"], "a") as log:
                log.write(json.dumps(argv) + "\\n")

            if argv == [
                "api",
                "repos/subzeroid/instagrapi/releases/latest",
                "--jq",
                ".tag_name",
            ]:
                if os.environ.get("GH_API_FAIL"):
                    sys.exit(1)
                print(os.environ["GH_LATEST_TAG"])
            elif argv[:2] == ["issue", "list"]:
                if os.environ.get("GH_ISSUE_LIST_FAIL"):
                    sys.exit(1)
                print(os.environ["GH_ISSUES"])
            elif argv[:2] == ["issue", "create"]:
                if os.environ.get("GH_ISSUE_CREATE_FAIL"):
                    sys.exit(1)
                body_file = argv.index("--body-file") + 1
                shutil.copyfile(argv[body_file], os.environ["GH_BODY_CAPTURE"])
                print("https://github.com/subzeroid/aiograpi/issues/123")
            else:
                sys.exit(2)
            """
        )
    )
    fake_gh.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "BASELINE_FILE": str(baseline_file),
        "GITHUB_REPOSITORY": "subzeroid/aiograpi",
        "GH_CALL_LOG": str(call_log),
        "GH_BODY_CAPTURE": str(body_capture),
        "GH_LATEST_TAG": "2.18.18",
        "GH_ISSUES": json.dumps([]),
    }
    return SimpleNamespace(
        baseline_file=baseline_file,
        body_capture=body_capture,
        call_log=call_log,
        env=environment,
    )


def _run_tracker(context, event_name, workflow_tag="", dispatch_tag="", **env_overrides):
    environment = {
        **context.env,
        "EVENT_NAME": event_name,
        "WORKFLOW_TAG": workflow_tag,
        "DISPATCH_TAG": dispatch_tag,
        **env_overrides,
    }
    return subprocess.run(
        [str(TRACKER)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _gh_calls(context):
    if not context.call_log.exists():
        return []
    return [json.loads(line) for line in context.call_log.read_text().splitlines()]


def test_tracker_syntax_is_compatible_with_macos_bash_3_2():
    result = subprocess.run(
        ["/bin/bash", "-n", str(TRACKER)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_upstream_instagrapi_baseline_is_recorded():
    assert aiograpi.__upstream_instagrapi_version__ == "2.18.19"


def test_upstream_sync_doc_matches_recorded_baseline():
    docs = Path("docs/upstream-sync.md").read_text()

    assert f"instagrapi {aiograpi.__upstream_instagrapi_version__}" in docs


def test_upstream_sync_workflow_is_scheduled_serialized_and_minimally_privileged():
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)

    assert workflow["on"]["schedule"] == [{"cron": "17 6 * * *"}]
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["on"]["workflow_dispatch"]["inputs"]["instagrapi_tag"]["required"] == "true"
    assert workflow["on"]["repository_dispatch"]["types"] == ["instagrapi_release"]
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}
    assert workflow["concurrency"] == {
        "group": "upstream-sync-tracker",
        "queue": "max",
        "cancel-in-progress": "false",
    }

    job = workflow["jobs"]["create-sync-issue"]
    assert job["runs-on"] == "ubuntu-latest"
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


def test_scheduled_tracker_skips_current_release(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "schedule")

    assert result.returncode == 0
    assert _gh_calls(context) == [
        [
            "api",
            "repos/subzeroid/instagrapi/releases/latest",
            "--jq",
            ".tag_name",
        ]
    ]
    assert "No upstream sync needed: 2.18.18 <= 2.18.18" in result.stdout


def test_explicit_older_target_skips_without_gh_calls(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "workflow_dispatch", workflow_tag="2.18.17")

    assert result.returncode == 0
    assert _gh_calls(context) == []
    assert "No upstream sync needed: 2.18.17 <= 2.18.18" in result.stdout


@pytest.mark.parametrize("target", ["", "v2.18.19", "2.18", "2.18.19-rc1"])
def test_invalid_explicit_target_is_rejected_without_gh_calls(tmp_path, target):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "workflow_dispatch", workflow_tag=target)

    assert result.returncode == 1
    assert "Invalid instagrapi target tag" in result.stderr
    assert _gh_calls(context) == []


def test_invalid_baseline_is_rejected_without_gh_calls(tmp_path):
    context = _tracker_context(tmp_path, baseline="not-a-version")

    result = _run_tracker(context, "workflow_dispatch", workflow_tag="2.18.19")

    assert result.returncode == 1
    assert "Invalid aiograpi upstream baseline" in result.stderr
    assert _gh_calls(context) == []


def test_invalid_baseline_with_mismatched_quotes_is_rejected(tmp_path):
    context = _tracker_context(tmp_path)
    context.baseline_file.write_text("__upstream_instagrapi_version__ = \"2.18.18'\n")

    result = _run_tracker(context, "workflow_dispatch", workflow_tag="2.18.19")

    assert result.returncode == 1
    assert "Invalid aiograpi upstream baseline" in result.stderr
    assert _gh_calls(context) == []


def test_comparison_error_does_not_report_a_new_release(tmp_path):
    context = _tracker_context(tmp_path)
    target = f"{'9' * 5000}.0.0"

    result = _run_tracker(context, "workflow_dispatch", workflow_tag=target)

    assert result.returncode != 0
    assert "New upstream release detected" not in result.stdout
    assert _gh_calls(context) == []


@pytest.mark.parametrize(
    ("target", "baseline"),
    [("2.18.19", "2.18.18"), ("2.19.0", "2.18.99")],
)
def test_valid_newer_target_reports_detection_and_creates_issue(tmp_path, target, baseline):
    context = _tracker_context(tmp_path, baseline=baseline)

    result = _run_tracker(context, "workflow_dispatch", workflow_tag=target)

    assert result.returncode == 0
    assert f"New upstream release detected: {baseline} -> {target}" in result.stdout
    assert _gh_calls(context)[0] == ISSUE_LIST_ARGS
    assert _gh_calls(context)[1][0:4] == [
        "issue",
        "create",
        "--repo",
        "subzeroid/aiograpi",
    ]


def test_release_api_failure_stops_before_issue_creation(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "schedule", GH_API_FAIL="1")

    assert result.returncode != 0
    assert _gh_calls(context) == [
        [
            "api",
            "repos/subzeroid/instagrapi/releases/latest",
            "--jq",
            ".tag_name",
        ]
    ]
    assert not context.body_capture.exists()


def test_invalid_scheduled_release_tag_is_rejected(tmp_path):
    context = _tracker_context(tmp_path)

    result = _run_tracker(context, "schedule", GH_LATEST_TAG="null")

    assert result.returncode == 1
    assert _gh_calls(context) == [
        [
            "api",
            "repos/subzeroid/instagrapi/releases/latest",
            "--jq",
            ".tag_name",
        ]
    ]
    assert "Invalid instagrapi target tag" in result.stderr


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


def test_saturated_issue_list_without_exact_match_fails_closed(tmp_path):
    context = _tracker_context(tmp_path)
    issues = json.dumps(
        [
            {
                "number": number,
                "title": f"Other issue {number}",
                "url": f"https://github.com/subzeroid/aiograpi/issues/{number}",
                "state": "OPEN",
            }
            for number in range(1, 1001)
        ]
    )

    result = _run_tracker(
        context,
        "workflow_dispatch",
        workflow_tag="2.18.19",
        GH_ISSUES=issues,
    )

    assert result.returncode != 0
    assert "::error::" in result.stderr
    assert _gh_calls(context) == [ISSUE_LIST_ARGS]
    assert not context.body_capture.exists()


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


def test_newer_target_requires_github_repository(tmp_path):
    context = _tracker_context(tmp_path)
    context.env.pop("GITHUB_REPOSITORY")

    result = _run_tracker(context, "workflow_dispatch", workflow_tag="2.18.19")

    assert result.returncode != 0
    assert "GITHUB_REPOSITORY is required" in result.stderr
    assert _gh_calls(context) == []
