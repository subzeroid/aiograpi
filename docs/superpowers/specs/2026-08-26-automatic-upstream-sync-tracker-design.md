# Automatic Upstream Sync Tracker Design

## Goal

Make the existing `Upstream Sync Tracker` create a visible `aiograpi` triage issue whenever a new stable `instagrapi` release appears, without requiring a cross-repository token or creating the same issue more than once.

## Chosen Approach

Run the tracker every day at 06:17 UTC from the `aiograpi` repository. Scheduled runs query GitHub's public latest-release endpoint for `subzeroid/instagrapi`. Existing `workflow_dispatch` and `repository_dispatch` entry points remain available and use their explicit tag inputs.

This approach accepts a delay of at most one day in exchange for using only the repository's standard `GITHUB_TOKEN`. It avoids maintaining a personal access token in `instagrapi` and keeps all issue-writing permissions inside `aiograpi`.

## Components

### Workflow

`.github/workflows/upstream-sync.yml` will:

- add a daily cron trigger at `17 6 * * *`;
- retain the existing manual and repository-dispatch triggers;
- keep `contents: read` and `issues: write` as its only permissions;
- check out the repository and invoke a repository-owned tracker script;
- serialize tracker runs with a workflow concurrency group so simultaneous triggers cannot race to create duplicate issues.

### Tracker Script

`scripts/upstream_sync_tracker.sh` will own the behavior that is currently embedded in the workflow. It will:

1. Resolve the target tag according to the event type:
   - `workflow_dispatch`: required workflow input;
   - `repository_dispatch`: required client-payload tag;
   - `schedule`: `gh api repos/subzeroid/instagrapi/releases/latest --jq .tag_name`.
2. Reject an empty tag or a tag outside the stable `X.Y.Z` format.
3. Read `__upstream_instagrapi_version__` from `aiograpi/__init__.py`.
4. Exit successfully when the target already matches the recorded baseline.
5. Search open `aiograpi` issues for the exact title `Sync aiograpi with instagrapi X.Y.Z` and exit successfully while printing its URL when found.
6. Create the issue only when the baseline differs and no exact open issue exists.

The generated issue will retain the current baseline, target tag, compare link, and port/release checklist.

## Data Flow

The schedule supplies only the event type. The script obtains the latest stable upstream tag from GitHub, reads the current local baseline, and makes one of three decisions: no-op because the baseline matches, no-op because a tracker issue already exists, or create one tracker issue. Manual and repository-dispatch events enter the same comparison and deduplication path after resolving their explicit tag.

## Error Handling and Security

- GitHub API, issue-list, or issue-create failures make the workflow fail visibly.
- Missing and malformed tags fail before any issue is written.
- Every shell expansion used as data is quoted, and a strict tag format prevents issue-title or URL injection.
- The tracker uses only `GITHUB_TOKEN`; no PAT, password, account credential, proxy, or Instagram session is introduced.
- Scheduled release discovery uses GitHub's `releases/latest` endpoint, which excludes drafts and prereleases.

## Testing

`tests/regression/test_upstream_sync_tracker.py` will execute the real tracker script against a temporary fake `gh` command and verify:

- a scheduled run queries the latest stable upstream release;
- an equal current/target baseline performs no issue lookup or creation;
- an existing exact-title issue prevents duplicate creation;
- a new target creates one issue with the expected title and body;
- missing or malformed tags fail without creating an issue.

The workflow file will also be checked for the cron trigger, concurrency guard, minimal permissions, and invocation of the tested script. Existing Ruff, regression, pre-commit, and strict documentation checks remain the landing gates.

## Non-goals

- Automatically porting upstream code or publishing `aiograpi`.
- Automatically closing sync issues.
- Creating a cross-repository token or changing `instagrapi` release workflows.
- Combining distinct upstream release tags into one mutable tracker issue.
