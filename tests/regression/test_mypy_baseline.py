"""The baseline gate must never turn an aborted mypy analysis green."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "status, output, expected",
    [
        (0, "Success: no issues found in 1 source file", 0),
        (1, "Found 2 errors in 1 file (checked 3 source files)", 0),
        (1, "Found 5 errors in 1 file (checked 3 source files)", 1),
        (2, "Found 2 errors in 1 file (errors prevented further checking)", 2),
        (2, "Success: no issues found in 1 source file", 2),
        (137, "process terminated", 137),
        (0, "unexpected empty analysis", 1),
        (1, "no recognizable summary", 1),
    ],
)
def test_gate_checks_exit_status_before_accepting_error_count(tmp_path, status, output, expected):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "check-mypy-baseline.sh"
    shutil.copyfile(Path(__file__).resolve().parents[2] / "scripts/check-mypy-baseline.sh", script)
    (tmp_path / ".mypy-baseline").write_text("4\n")
    (tmp_path / "mypy.py").write_text(
        "import os, sys\nprint(os.environ['SYNTHETIC_MYPY_OUTPUT'])\nsys.exit(int(os.environ['SYNTHETIC_MYPY_STATUS']))\n"
    )
    env = dict(os.environ, PYTHON=sys.executable, SYNTHETIC_MYPY_STATUS=str(status), SYNTHETIC_MYPY_OUTPUT=output)
    result = subprocess.run(["bash", str(script)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == expected, result.stdout + result.stderr
    if expected:
        assert "::error::" in result.stderr
