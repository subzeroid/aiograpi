import json
import os
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

import aiograpi

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "scripts" / "upstream_sync_tracker.sh"


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
    assert aiograpi.__upstream_instagrapi_version__ == "2.18.18"


def test_upstream_sync_doc_matches_recorded_baseline():
    docs = Path("docs/upstream-sync.md").read_text()

    assert f"instagrapi {aiograpi.__upstream_instagrapi_version__}" in docs


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
