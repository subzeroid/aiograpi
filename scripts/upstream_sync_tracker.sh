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
    r'^__upstream_instagrapi_version__\s*=\s*["\']([^"\']+)["\']\s*$',
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

if python3 - "$TARGET_TAG" "$BASELINE" <<'PY'
import sys

target = tuple(map(int, sys.argv[1].split(".")))
baseline = tuple(map(int, sys.argv[2].split(".")))
sys.exit(0 if target <= baseline else 1)
PY
then
  echo "No upstream sync needed: $TARGET_TAG <= $BASELINE"
else
  echo "New upstream release detected: $BASELINE -> $TARGET_TAG"
fi
