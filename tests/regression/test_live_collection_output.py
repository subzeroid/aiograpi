"""The automatic collection live step must publish aggregates, not raw diagnostics."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github/workflows/python-package.yml"
SECRET = "synthetic-collection-diagnostic-secret"
SOURCE = """import logging
import os
import sys
import warnings
import pytest

SECRET = "synthetic-collection-diagnostic-secret"
MODE = os.environ["SYNTHETIC_COLLECTION_MODE"]

def noise():
    print(SECRET)
    print(SECRET, file=sys.stderr)
    os.write(1, SECRET.encode())
    os.write(2, SECRET.encode())
    warnings.warn(SECRET)
    try:
        raise RuntimeError(SECRET)
    except RuntimeError:
        logging.exception(SECRET)

if MODE == "collection_error":
    noise()
    raise RuntimeError(SECRET)

@pytest.fixture(autouse=True)
def fixture():
    if MODE == "setup_error":
        noise()
        raise RuntimeError(SECRET)
    yield
    if MODE == "teardown_error":
        noise()
        raise RuntimeError(SECRET)

def test_case():
    noise()
    if MODE == "failure":
        raise RuntimeError(SECRET)
    if MODE == "skip":
        pytest.skip(SECRET)
"""


@pytest.mark.parametrize(
    "mode, status, summaries",
    [
        ("success", 0, ["1 passed"]),
        ("failure", 1, ["1 failed"]),
        ("skip", 0, ["1 skipped"]),
        ("collection_error", 2, ["1 error"]),
        ("setup_error", 1, ["1 error"]),
        ("teardown_error", 1, ["1 passed", "1 error"]),
    ],
)
def test_collection_ci_command_suppresses_raw_output_and_preserves_results(tmp_path, mode, status, summaries):
    workflow = yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)
    step = next(
        step
        for step in workflow["jobs"]["live-test"]["steps"]
        if step.get("name") == "Run collection pagination live test"
    )
    command = shlex.split(step["run"])
    assert command[:2] == ["PYTHONPATH=.", "pytest"]
    assert command[-1] == (
        "tests/live/test_collection.py::ClientCollectionLiveTestCase::test_collection_medias_by_name_pagination_live"
    )
    (tmp_path / "test_case.py").write_text(SOURCE)
    # Exercise overrides so configuration cannot re-enable live logs or skip reasons.
    (tmp_path / "pytest.ini").write_text("[pytest]\nlog_cli = true\nlog_cli_level = DEBUG\naddopts = -ra\n")
    env = dict(os.environ, SYNTHETIC_COLLECTION_MODE=mode, PYTEST_ADDOPTS="")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", *command[2:-1], "test_case.py"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    output = result.stdout + result.stderr
    assert SECRET not in output
    assert "Traceback" not in output
    assert "Captured" not in output
    assert result.returncode == status, output
    for summary in summaries:
        assert summary in output
