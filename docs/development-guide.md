# Development Guide

Welcome! Thank you for wanting to make the project better. This section provides an overview on how repository structure
and how to work with the code base.

Before you dive into this, it is best to read:

* The [Contributing guide](https://github.com/subzeroid/aiograpi/blob/main/CONTRIBUTING.md)

## Local Environment

Use a virtual environment and install the project from `pyproject.toml` with test extras:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
pre-commit install
```

If you use [uv][uv-docs], keep the same `pyproject.toml` source of truth:

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[test]"
pre-commit install
```

## Debugging

Python's built-in [pdb][pdb-docs] debugger is enough for most local debugging. You can create a breakpoint anywhere in
the code:

```python
def my_function():
    breakpoint()
    ...
```

When the code reaches the breakpoint, it will drop into an interactive debugger.

See the documentation on [pdb][pdb-docs] for more information.

## Testing

You'll be unable to merge code unless linting and tests pass. The main local checks are:

```bash
pytest -sv tests/regression
ruff check .
ruff format --check .
./scripts/check-mypy-baseline.sh
bandit -c pyproject.toml -r aiograpi
pip-audit --strict .
mkdocs build --strict
```

The mypy gate targets Python 3.10 and runs under Python 3.10 in CI so dependency type stubs match that target. For local parity, create the development environment with `python3.10 -m venv .venv` or `uv venv --python 3.10` and install the test extras. The gate compares only completed analysis with `.mypy-baseline`; aborted analysis and unrecognized output fail instead of being accepted as a low error count.

To apply automatic lint and formatting fixes locally:

```bash
ruff check . --fix
ruff format .
```

Generally we should endeavor to write tests for every feature. Every new feature branch should increase the test
coverage rather than decreasing it.

We use [pytest][pytest-docs] as our testing framework.

To include the optional private curl transport tests, install both extras with `python -m pip install -e ".[test,curl]"`, then run `python -m pytest -q tests/regression/test_private_transport.py tests/regression/test_private_transport_wire.py`. These tests use local TLS/HTTP2 servers and need no Instagram account.

#### Stages

To customize / override a specific testing stage, please read the documentation specific to that tool:

1. [PyTest][pytest-docs]
2. [Ruff][ruff-docs]
3. [Bandit][bandit-docs]

### `pyproject.toml`

Setuptools is used to package the library through `pyproject.toml`.

`pyproject.toml` is the source of truth for package metadata, runtime dependencies, and test/development extras.

### Requirements

* `[project].dependencies` lists runtime dependencies imported by the library.
* `[project.optional-dependencies].test` lists tools needed for tests, linting, docs, and local development.
* Runtime dependency lower bounds should stay at the currently tested/security-patched version, with an upper bound before the next breaking release line.
* Android-specific pins are allowed when the mobile Python ecosystem needs an exact wheel-compatible version, for example the Termux pydantic-core wheel constraint.

Publishing is handled by the tag-based `publish.yml` workflow. Pushes and pull requests run the package workflow first;
maintainers cut a version tag only after the checks are green.

## Continuous Integration Pipeline

The `Package` workflow runs pip-audit, Bandit, Ruff, the mypy regression gate, network-free regression tests, and docs builds. Its private curl job checks minimum and current curl_cffi on Python 3.10 and 3.14. On canonical repository pushes it also runs `tests/live/smoke.py` against the pooled live-account endpoint configured in `TEST_ACCOUNTS_URL`.

Realtime MQTT/FBNS live tests also use `TEST_ACCOUNTS_URL` for pooled accounts. Set `IG_REALTIME_PROXY` when the account
HTTP proxy can log in but cannot open a CONNECT tunnel to Instagram's MQTT hosts; the realtime tests use that proxy only
for the MQTT socket and keep the account proxy for normal private API calls.

The `Publish to PyPI` workflow runs only for version tags such as `0.9.0`. It verifies the tag matches
`pyproject.toml`, builds the wheel and sdist, publishes through PyPI trusted publishing, creates the GitHub release, and
publishes versioned docs with `mike`.

The `Upstream Sync Tracker` workflow can be triggered manually or by repository dispatch when `instagrapi` publishes a
new release. It creates a tracking issue with the current async-port baseline and the target upstream tag.

## Controlled Login Profile Research

Maintainers can use `scripts/research_login_matrix.py` to compare login outcomes for a reused device profile and a fresh profile. This is an opt-in diagnostic experiment for accounts and networks you control, not a CI test. Repeated login attempts can trigger Instagram checkpoints or temporary restrictions, so start with one trial and inspect the result before increasing the count.

```bash
IG_RUN_LOGIN_MATRIX=1 \
TEST_ACCOUNTS_URL="https://your-controlled-pool.example/accounts" \
python scripts/research_login_matrix.py --mode both --count 1
```

The account-pool URL must use HTTPS with normal certificate verification. Redirects are rejected. `stable` retains only device/profile fields from the stored client settings; it drops sessions and other authentication state. `fresh` creates a client without stored settings. The default `separate` pairing uses different accounts for the two conditions. `--pairing crossover` uses the same account for both conditions, but the first login can influence the second.

Attempts run sequentially. The default cooldown is 30 seconds, the minimum is 10 seconds, and one invocation is limited to ten total login attempts. Use `--login-timeout` to bound each attempt and `--output` to select the append-only JSONL file. Non-finite numeric values are rejected.

The output file is created with owner-only permissions. The script refuses symlinks and existing files accessible by group or other users, and it verifies the opened file before writing. Records include a random run ID, trial and attempt indexes, mode, status, exception class, elapsed time, a proxy-used boolean, and keyed per-run device-profile digests. They never include usernames, passwords, TOTP secrets or codes, sessions, proxy values, account-pool URLs, exception messages, or response bodies. Client and request loggers are muted during attempts so library warnings cannot print raw responses. The digest key is not saved, so device identifiers cannot be correlated across separate runs. The default `login-matrix.jsonl` output is ignored by Git.

Individual login errors are experiment results and do not stop the matrix. Invalid configuration, unsafe output paths, account-pool failures, and malformed account records stop the run with a non-zero exit status. GitHub Actions never invokes this script.

[pdb-docs]: https://docs.python.org/3/library/pdb.html
[pytest-docs]: https://docs.pytest.org/en/latest/
[ruff-docs]: https://docs.astral.sh/ruff/
[uv-docs]: https://docs.astral.sh/uv/
[bandit-docs]: https://bandit.readthedocs.io/en/stable/
[sem-ver]: https://semver.org/
[pypi]: https://pypi.org/project/aiograpi/
