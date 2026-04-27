<!-- Thanks for the PR. Keep it focused — small PRs land faster than sweeping ones. -->

## What

<!-- One or two sentences. What does this change? -->

## Why

<!-- Link the issue (Closes #123) or explain the motivation. -->

## Notes for reviewers

<!-- Anything non-obvious: API changes, migration steps, follow-ups deferred, alternatives rejected, IG behavior you observed. -->

## Checklist

- [ ] Tests added or updated (see existing classes in `tests.py`)
- [ ] Unit tests pass (or trust CI)
- [ ] Mypy gate clean: `./scripts/check-mypy-baseline.sh`
- [ ] Docs updated if user-facing (`docs/`, `README.md`, `CHANGELOG.md`)
- [ ] Migration note in `CHANGELOG.md` if breaking
- [ ] No secrets, tokens, sessionids, or proxy URLs in commits or logs
