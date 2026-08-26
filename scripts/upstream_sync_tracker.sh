#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE_FILE="${BASELINE_FILE:-$ROOT/aiograpi/__init__.py}"
EVENT_NAME="${EVENT_NAME:-}"
WORKFLOW_TAG="${WORKFLOW_TAG:-}"
DISPATCH_TAG="${DISPATCH_TAG:-}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-}"
UPSTREAM_REPOSITORY="subzeroid/instagrapi"
VERSION_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+$'

case "$EVENT_NAME" in
  schedule)
    TARGET_TAG="$(gh api "repos/$UPSTREAM_REPOSITORY/releases/latest" --jq .tag_name)"
    ;;
  workflow_dispatch)
    TARGET_TAG="$WORKFLOW_TAG"
    ;;
  repository_dispatch)
    TARGET_TAG="$DISPATCH_TAG"
    ;;
  *)
    echo "Unsupported or missing event: $EVENT_NAME" >&2
    exit 1
    ;;
esac

if ! [[ "$TARGET_TAG" =~ $VERSION_PATTERN ]]; then
  echo "Invalid instagrapi target tag: $TARGET_TAG" >&2
  exit 1
fi

read_baseline() {
  python3 - "$BASELINE_FILE" <<'PY'
import re
import sys
from pathlib import Path

match = re.search(
    r'^__upstream_instagrapi_version__\s*=\s*"([^"]+)"\s*$',
    Path(sys.argv[1]).read_text(),
    re.MULTILINE,
)
if match:
    print(match.group(1))
PY
}

BASELINE="$(read_baseline)"

if ! [[ "$BASELINE" =~ $VERSION_PATTERN ]]; then
  echo "Invalid aiograpi upstream baseline: $BASELINE" >&2
  exit 1
fi

compare_versions() {
  python3 - "$TARGET_TAG" "$BASELINE" <<'PY'
import sys

target = tuple(map(int, sys.argv[1].split(".")))
baseline = tuple(map(int, sys.argv[2].split(".")))
print("not-newer" if target <= baseline else "newer")
PY
}

VERSION_ORDER="$(compare_versions)"

case "$VERSION_ORDER" in
  not-newer)
    echo "No upstream sync needed: $TARGET_TAG <= $BASELINE"
    ;;
  newer)
    echo "New upstream release detected: $BASELINE -> $TARGET_TAG"
    ;;
  *)
    echo "Invalid version comparison result: $VERSION_ORDER" >&2
    exit 1
    ;;
esac

if [[ "$VERSION_ORDER" != "newer" ]]; then
  exit 0
fi

if [[ -z "$GITHUB_REPOSITORY" ]]; then
  echo "::error::GITHUB_REPOSITORY is required" >&2
  exit 1
fi

TARGET_REPOSITORY="$GITHUB_REPOSITORY"
ISSUE_TITLE="Sync aiograpi with instagrapi $TARGET_TAG"
ISSUES_FILE="$(mktemp)"
BODY_FILE=""

cleanup() {
  rm -f "$ISSUES_FILE"
  if [[ -n "$BODY_FILE" ]]; then
    rm -f "$BODY_FILE"
  fi
}
trap cleanup EXIT

if ! gh issue list \
  --repo "$TARGET_REPOSITORY" \
  --state all \
  --limit 1000 \
  --json number,title,url,state > "$ISSUES_FILE"; then
  echo "::error::Failed to list existing upstream sync issues" >&2
  exit 1
fi

find_existing_issue() {
  python3 - "$ISSUES_FILE" "$ISSUE_TITLE" <<'PY'
import json
import sys
from pathlib import Path

issues = json.loads(Path(sys.argv[1]).read_text())
title = sys.argv[2]
for issue in issues:
    if issue.get("title") == title:
        print(f"match\t{issue.get('state', '')}\t{issue.get('url', '')}")
        sys.exit(0)

if len(issues) == 1000:
    print("saturated")
PY
}

if ! EXISTING_ISSUE="$(find_existing_issue)"; then
  echo "::error::Failed to inspect existing upstream sync issues" >&2
  exit 1
fi

if [[ -n "$EXISTING_ISSUE" ]]; then
  IFS=$'\t' read -r ISSUE_RESULT EXISTING_STATE EXISTING_URL <<< "$EXISTING_ISSUE"
  case "$ISSUE_RESULT" in
    saturated)
      echo "::error::Issue list reached its limit without an exact title match" >&2
      exit 1
      ;;
    match)
      if [[ "$EXISTING_STATE" == "CLOSED" ]]; then
        echo "::warning::Upstream sync issue is already closed while the baseline is behind: $EXISTING_URL" >&2
      else
        echo "Upstream sync issue already exists: $EXISTING_URL"
      fi
      exit 0
      ;;
    *)
      echo "::error::Invalid existing upstream sync issue result" >&2
      exit 1
      ;;
  esac
fi

BODY_FILE="$(mktemp)"
{
  printf '%s\n\n' "A new instagrapi release needs aiograpi triage."
  printf 'Current aiograpi baseline: %s\n' "$BASELINE"
  printf 'Target instagrapi tag: %s\n' "$TARGET_TAG"
  printf 'Compare: https://github.com/subzeroid/instagrapi/compare/%s...%s\n\n' "$BASELINE" "$TARGET_TAG"
  printf '%s\n' "Checklist:"
  printf '%s\n' "- [ ] Review instagrapi release notes and changed files."
  printf '%s\n' "- [ ] Decide which changes are async-portable."
  printf '%s\n' "- [ ] Port features/fixes with regression tests."
  printf '%s\n' "- [ ] Update docs and aiograpi upstream baseline."
  printf '%s\n' "- [ ] Run local checks and CI."
  printf '%s\n' "- [ ] Publish an aiograpi release or record why no release is needed."
} > "$BODY_FILE"

if ! gh issue create \
  --repo "$TARGET_REPOSITORY" \
  --title "$ISSUE_TITLE" \
  --body-file "$BODY_FILE"; then
  echo "::error::Failed to create upstream sync issue" >&2
  exit 1
fi
