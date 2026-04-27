#!/usr/bin/env bash
# Mypy regression gate. Counts mypy errors against the recorded baseline
# and fails if the count goes up. Strict-pass is years away (legacy
# upstream port has 1000+ untyped functions, mostly cross-mixin attribute
# refs that need Protocol scaffolding) — this gate just stops the bleeding
# while we chip away at it.
#
# To accept a lower count after fixing errors, update .mypy-baseline.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASELINE_FILE="$ROOT/.mypy-baseline"

if [ ! -f "$BASELINE_FILE" ]; then
  echo "::error::missing $BASELINE_FILE" >&2
  exit 2
fi
BASELINE=$(tr -d '[:space:]' < "$BASELINE_FILE")

# Run mypy and capture last summary line. mypy returns nonzero when errors
# exist — that's expected, so don't propagate via pipefail.
set +e
OUTPUT=$(cd "$ROOT" && mypy aiograpi/ 2>&1)
set -e

SUMMARY=$(printf '%s\n' "$OUTPUT" | tail -1)
CURRENT=$(printf '%s' "$SUMMARY" | grep -oE 'Found [0-9]+ error' | grep -oE '[0-9]+' | head -1 || echo "0")

echo "mypy baseline: $BASELINE"
echo "mypy current : $CURRENT"

if [ "$CURRENT" -gt "$BASELINE" ]; then
  echo "::error::mypy errors increased: $CURRENT > $BASELINE (regression)" >&2
  echo "Recent diff (showing first 30 errors of $CURRENT):" >&2
  printf '%s\n' "$OUTPUT" | grep -E '^aiograpi/' | head -30 >&2
  exit 1
fi

if [ "$CURRENT" -lt "$BASELINE" ]; then
  echo "::notice::mypy errors decreased: $CURRENT < $BASELINE — drop the baseline:"
  echo "  echo '$CURRENT' > .mypy-baseline"
fi
