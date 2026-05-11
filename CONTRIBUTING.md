# Contributing

Thanks for helping improve `aiograpi`.

Before starting a larger change, open or comment on a GitHub issue so maintainers can confirm the direction. For usage
questions and support, use [GitHub Discussions](https://github.com/subzeroid/aiograpi/discussions) or the Telegram
support group [aiograpi_support](https://t.me/aiograpi_support).

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) in all project spaces.

## Development Setup

Use a virtual environment and install the package from `pyproject.toml` with test extras:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
pre-commit install
```

If you use `uv`, keep the same `pyproject.toml` source of truth:

```bash
uv venv
source .venv/bin/activate
uv sync --extra test
pre-commit install
```

`pipx` is useful for globally installing `pre-commit`:

```bash
pipx install pre-commit
```

Do not use `pipx` to install `aiograpi`; it is a library package, not a command-line application.

## Tests and Quality Checks

Run these checks before opening a pull request:

```bash
ruff check .
ruff format --check .
pytest -q tests.py tests/regression
./scripts/check-mypy-baseline.sh
bandit -c pyproject.toml -r aiograpi
mkdocs build --strict
pre-commit run --all-files
```

To apply automatic lint and formatting fixes:

```bash
ruff check . --fix
ruff format .
```

Regression tests live in `tests.py` and `tests/regression/`. Live-account tests live in `tests/live/` and require
`TEST_ACCOUNTS_URL`; do not run or modify live tests in a way that prints credentials, proxies, sessions, or the account
URL.

## Pull Request Checklist

1. Branch from `main` and keep the change scoped.
2. Add or update regression tests for changed behavior.
3. Add focused live tests when the change depends on Instagram's live API behavior.
4. Update `README.md` or `docs/` when public APIs, setup steps, troubleshooting, or user-visible behavior changes.
5. Keep dependencies in `pyproject.toml`; do not add root `requirements*.txt`.
6. Keep style and linting under Ruff; do not reintroduce `.flake8`, `.isort.cfg`, or Black-only config.
7. Do not add Docker files unless the repository intentionally restores a maintained Docker workflow.

Maintainers handle release versioning and publishing unless a maintainer asks for a version bump in the PR.

## Project Documentation

- User guide: [subzeroid.github.io/aiograpi](https://subzeroid.github.io/aiograpi/)
- Development guide: [development-guide](https://subzeroid.github.io/aiograpi/latest/development-guide/)
- Upstream sync notes: [upstream-sync](https://subzeroid.github.io/aiograpi/latest/upstream-sync/)

## Release Commands

Maintainer-only release flow:

```bash
git tag -a 0.x.y -m "Release 0.x.y"
git push origin 0.x.y
```

The `publish.yml` workflow builds the distributions, publishes to PyPI via trusted publishing, creates the GitHub
release, and publishes versioned docs.
