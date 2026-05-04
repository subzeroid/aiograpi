#!/usr/bin/env bash

set -eo pipefail

NEW_VERSION="${1}"
PREV_LATEST="$(mike list --json | jq --raw-output '.[] | select(.aliases == ["latest"]) | .version')"

if [[ "${PREV_LATEST}" == "" ]]; then
  echo "No previous version found using the latest alias. Nothing to retitle."
else
  echo "mike retitle --message \"Remove latest from title of ${PREV_LATEST}\" \"${PREV_LATEST}\" \"${PREV_LATEST}\""
  mike retitle --message "Remove latest from title of ${PREV_LATEST}" "${PREV_LATEST}" "${PREV_LATEST}"
fi
echo "mike deploy --update-aliases --title \"${NEW_VERSION} (latest)\" \"${NEW_VERSION}\" \"latest\""
mike deploy --update-aliases --title "${NEW_VERSION} (latest)" "${NEW_VERSION}" "latest"

# Idempotent: writes a root-level redirect index.html pointing at /latest/
# so https://subzeroid.github.io/aiograpi/ resolves instead of returning 404.
echo "mike set-default latest"
mike set-default latest
