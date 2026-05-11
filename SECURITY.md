# Security Policy

## Supported Versions

Only the latest released version is supported for security fixes.

| Version    | Supported          |
| ---------- | ------------------ |
| Latest release | :white_check_mark: |
| Older releases | :x:                |

## Published Advisories

[`GHSA-7mw3-79jq-xc7f`](https://github.com/subzeroid/aiograpi/security/advisories/GHSA-7mw3-79jq-xc7f)
affects `aiograpi>=0.6.6,<0.7.2`: those releases shipped metadata that resolved `orjson==3.11.4` because of a
duplicate dependency list in the old `setup.py`. The affected PyPI releases are yanked. Upgrade to the latest release,
or at minimum `aiograpi>=0.7.2`, which uses the fixed `pyproject.toml` dependency metadata and resolves
`orjson==3.11.8`.

## Reporting a Vulnerability

Do not include account credentials, session IDs, proxy credentials, or private tokens in public issues.

For sensitive reports, use GitHub private vulnerability reporting if it is available for this repository. For
non-sensitive security bugs, open an issue at https://github.com/subzeroid/aiograpi/issues.

For urgent maintainer contact, use the Telegram support group [aiograpi_support](https://t.me/aiograpi_support).
