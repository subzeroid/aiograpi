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
bandit -c pyproject.toml -r aiograpi
pip-audit --strict .
mkdocs build --strict
```

To apply automatic lint and formatting fixes locally:

```bash
ruff check . --fix
ruff format .
```

Generally we should endeavor to write tests for every feature. Every new feature branch should increase the test
coverage rather than decreasing it.

We use [pytest][pytest-docs] as our testing framework.

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

The `Package` workflow runs pip-audit, Bandit, Ruff, the mypy regression gate, network-free regression tests, and docs
builds. On canonical repository pushes it also runs `tests/live/smoke.py` against the pooled live-account endpoint
configured in `TEST_ACCOUNTS_URL`.

Realtime MQTT/FBNS live tests also use `TEST_ACCOUNTS_URL` for pooled accounts. Set `IG_REALTIME_PROXY` when the account
HTTP proxy can log in but cannot open a CONNECT tunnel to Instagram's MQTT hosts; the realtime tests use that proxy only
for the MQTT socket and keep the account proxy for normal private API calls.

The `Publish to PyPI` workflow runs only for version tags such as `0.9.0`. It verifies the tag matches
`pyproject.toml`, builds the wheel and sdist, publishes through PyPI trusted publishing, creates the GitHub release, and
publishes versioned docs with `mike`.

The `Upstream Sync Tracker` workflow can be triggered manually or by repository dispatch when `instagrapi` publishes a
new release. It creates a tracking issue with the current async-port baseline and the target upstream tag.

[pdb-docs]: https://docs.python.org/3/library/pdb.html
[pytest-docs]: https://docs.pytest.org/en/latest/
[ruff-docs]: https://docs.astral.sh/ruff/
[uv-docs]: https://docs.astral.sh/uv/
[bandit-docs]: https://bandit.readthedocs.io/en/stable/
[sem-ver]: https://semver.org/
[pypi]: https://pypi.org/project/aiograpi/
