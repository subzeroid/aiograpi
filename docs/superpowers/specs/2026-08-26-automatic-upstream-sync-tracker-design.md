# Automatic Upstream Sync Tracker Design

## Goal

Make the existing `Upstream Sync Tracker` create a visible `aiograpi` triage issue whenever a newer stable `instagrapi` release appears, without requiring a cross-repository token or creating the same issue more than once, even if the earlier issue was closed.

## Chosen Approach

Run the tracker every day at 06:17 UTC from the `aiograpi` repository. Scheduled runs query GitHub's public latest-release endpoint for `subzeroid/instagrapi`. The current upstream release process was verified to publish stable GitHub Releases, including `2.18.18`. Existing `workflow_dispatch` and `repository_dispatch` entry points remain available and use their explicit tag inputs.

This approach accepts a normal detection delay of up to one day in exchange for using only the repository's standard `GITHUB_TOKEN`. GitHub schedules are best-effort: they can be delayed or dropped during high load, run only from the default branch, and are disabled for public repositories after 60 days without repository activity. It avoids maintaining a personal access token in `instagrapi` and keeps all issue-writing permissions inside `aiograpi`.

## Components

### Workflow

`.github/workflows/upstream-sync.yml` will:

- add a daily cron trigger at `17 6 * * *`;
- retain the existing manual and repository-dispatch triggers;
- keep `contents: read` and `issues: write` as its only permissions;
- use a 10-minute job timeout;
- check out the default branch with persisted Git credentials disabled so every trigger reads the canonical baseline;
- invoke a repository-owned tracker script;
- serialize every branch and event through the fixed `upstream-sync-tracker` concurrency group with `queue: max` and `cancel-in-progress: false`, so simultaneous triggers cannot race or replace an already pending run.

### Tracker Script

`scripts/upstream_sync_tracker.sh` will own the behavior that is currently embedded in the workflow. It will:

1. Resolve the target tag according to the event type:
   - `workflow_dispatch`: required workflow input;
   - `repository_dispatch`: required client-payload tag;
   - `schedule`: `gh api repos/subzeroid/instagrapi/releases/latest --jq .tag_name`.
2. Reject an empty tag or a tag outside the anchored stable `X.Y.Z` format. Invalid scheduled discovery also fails visibly instead of silently disabling tracking.
3. Read `__upstream_instagrapi_version__` from `aiograpi/__init__.py` with `python3` and validate it against the same format.
4. Compare both tags as integer version tuples and exit successfully when the target is equal to or older than the recorded baseline.
5. List issues with `gh issue list --repo "$GITHUB_REPOSITORY" --state all --limit 1000 --json number,title,url,state`, then perform a byte-exact title comparison for `Sync aiograpi with instagrapi X.Y.Z` locally. GitHub Search is not used because its index is eventually consistent and its matching is not exact.
6. Exit successfully while printing the existing issue URL when an exact open issue exists. Do the same with a warning when the match is closed, so a manually closed or superseded tracker is not recreated every day.
7. Create the issue only when the target is newer and no exact issue exists in any state.

The generated issue will retain the current baseline, target tag, compare link, and port/release checklist. Its temporary body file will be removed with an exit trap.

## Data Flow

The schedule supplies only the event type. The script obtains the latest stable upstream tag from GitHub, reads the canonical default-branch baseline, and makes one of three decisions: no-op because the baseline is current or newer, no-op because a tracker issue already exists, or create one tracker issue. Manual and repository-dispatch events enter the same comparison and deduplication path after resolving their explicit tag.

## Error Handling and Security

- GitHub release API, issue-list, or issue-create failures make the workflow fail visibly.
- Missing and malformed target or baseline tags fail before issue lookup or creation.
- Every shell expansion used as data is quoted, and a strict tag format prevents issue-title or URL injection.
- The tracker uses only `GITHUB_TOKEN`; no PAT, password, account credential, proxy, or Instagram session is introduced.
- Scheduled release discovery uses GitHub's `releases/latest` endpoint, which excludes drafts and prereleases.
- Workflow inputs reach the shell only through `env:` variables, never through direct expression interpolation inside `run:` blocks.

## Testing

The existing `tests/regression/test_upstream_sync.py` will be extended to execute the real tracker script against a temporary fake `gh` command and verify:

- a scheduled run queries the latest stable upstream release;
- equal and older target versions perform no issue lookup or creation;
- malformed or missing target and baseline tags fail before invoking `gh` for issue operations;
- upstream release lookup and issue-list failures return non-zero without creating an issue;
- existing exact-title issues in open and closed states prevent duplicate creation;
- near-match titles such as other patch versions and prerelease suffixes do not suppress creation;
- a new target creates one issue with the expected title and body;
- the fake CLI records and verifies the exact release API, issue-list, and issue-create arguments.

The workflow file will also be parsed and checked for the cron trigger, fixed queued concurrency guard, minimal permissions, timeout, canonical checkout configuration, absence of direct expressions inside `run:` blocks, and invocation of the tested script. Existing Ruff, regression, pre-commit, and strict documentation checks remain the landing gates.

## Non-goals

- Automatically porting upstream code or publishing `aiograpi`.
- Automatically closing sync issues.
- Creating a cross-repository token or changing `instagrapi` release workflows.
- Combining distinct upstream release tags into one mutable tracker issue.
- Creating separate issues for intermediate upstream releases published between scheduled runs; the newest release's compare link covers the skipped range.
- Generating keepalive commits solely to prevent GitHub's 60-day inactivity shutdown; that platform behavior is documented instead.
