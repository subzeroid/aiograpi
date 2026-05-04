#!/usr/bin/env bash

set -eo pipefail

echo "::group::Configure Git User"
"${GITHUB_ACTION_PATH}/configure_git_user.sh"
echo "::endgroup::"

echo "::group::Pull down latest docs commit"
git fetch --no-tags --prune --progress --no-recurse-submodules --depth=1 origin gh-pages
echo "::endgroup::"

echo "::group::Publish documentation"
if [[ "${NEW_VERSION}" == "false" ]]; then
  if [[ "${VERSION_NAME}" == "" ]]; then
    echo "::error::'version_name' must be specified when 'NEW_VERSION' is false."
    exit 1
  fi
  echo "mike deploy \"${VERSION_NAME}\""
  mike deploy "${VERSION_NAME}"
elif [[ "${RELEASE_TAG}" == "" ]]; then
  echo "::error::new_version requires RELEASE_TAG (release event or tag push)."
  exit 1
else
  # Strip a leading "v" if present (e.g. "v0.8.9" -> "0.8.9");
  # aiograpi's tags are unprefixed ("0.8.9") so this is a no-op there.
  "${GITHUB_ACTION_PATH}/update_docs_for_version.sh" "${RELEASE_TAG#v}"
fi
echo "git push origin gh-pages"
git push origin gh-pages
echo "::endgroup::"
