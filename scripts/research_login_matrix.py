"""Opt-in login experiment for controlled device-profile research.

The tool records pseudonymous outcome metadata only. Run it exclusively with
accounts and networks you control.
"""

import argparse
import asyncio
import hashlib
import hmac
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiograpi import Client

MAX_ATTEMPTS = 10
MIN_COOLDOWN_SECONDS = 10.0
DEVICE_SETTING_KEYS = {
    "country",
    "country_code",
    "device_settings",
    "locale",
    "timezone_offset",
    "user_agent",
    "uuids",
}


@dataclass(frozen=True)
class Job:
    trial: int
    account_index: int
    mode: str


def build_accounts_url(url: str, count: int) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "count"]
    query.append(("count", str(count)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def device_only_settings(settings: dict) -> dict:
    return {key: value for key, value in settings.items() if key in DEVICE_SETTING_KEYS}


def build_jobs(accounts: list[dict], modes: tuple[str, ...], pairing: str, count: int) -> list[Job]:
    requested = count if pairing == "crossover" else count * len(modes)
    if len(accounts) < requested:
        raise ValueError(f"need {requested} accounts; endpoint returned {len(accounts)}")

    jobs = []
    for trial in range(count):
        ordered_modes = modes if trial % 2 == 0 else tuple(reversed(modes))
        for offset, mode in enumerate(ordered_modes):
            account_index = trial if pairing == "crossover" else trial * len(modes) + offset
            jobs.append(Job(trial=trial, account_index=account_index, mode=mode))
    return jobs


def digest_profile_value(key: bytes, value: object) -> str:
    return hmac.new(key, str(value).encode(), hashlib.sha256).hexdigest()[:16]


def profile(client: Client, digest_key: bytes) -> dict[str, str]:
    return {
        "uuid": digest_profile_value(digest_key, client.uuid),
        "android_device_id": digest_profile_value(digest_key, client.android_device_id),
        "user_agent": digest_profile_value(digest_key, client.user_agent),
    }


def fetch_accounts(url: str, count: int, *, opener=urllib.request.urlopen) -> list[dict]:
    request = urllib.request.Request(
        build_accounts_url(url, count),
        headers={"User-Agent": "aiograpi-login-matrix"},
    )
    with opener(request, timeout=30) as response:
        payload = json.loads(response.read())

    accounts = payload if isinstance(payload, list) else payload.get("accounts") if isinstance(payload, dict) else None
    if not isinstance(accounts, list):
        raise ValueError("account pool response must contain an accounts list")
    for account in accounts:
        if not isinstance(account, dict) or not account.get("username") or not account.get("password"):
            raise ValueError("account pool records must contain username and password")
    return accounts


async def attempt(
    job: Job,
    account: dict,
    *,
    run_id: str,
    digest_key: bytes,
    pairing: str,
    login_timeout: float,
    client_factory=Client,
) -> dict:
    settings = dict(account.get("client_settings") or account.get("settings") or {})
    totp_seed = settings.pop("totp_seed", None) or account.get("totp_seed")
    client = client_factory(
        settings=device_only_settings(settings) if job.mode == "stable" else None,
        proxy=account.get("proxy"),
    )
    result = {
        "run_id": run_id,
        "trial": job.trial,
        "mode": job.mode,
        "pairing": pairing,
        "proxy_used": bool(account.get("proxy")),
        "profile_before": profile(client, digest_key),
        "status": "error",
    }
    login_kwargs = {}
    if totp_seed:
        login_kwargs["verification_code"] = client.totp_generate_code(totp_seed)

    started = time.monotonic()
    try:
        async with client.public, client.private, client.graphql:
            await asyncio.wait_for(
                client.login(account["username"], account["password"], **login_kwargs),
                timeout=login_timeout,
            )
        result["status"] = "ok"
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    finally:
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        result["profile_after"] = profile(client, digest_key)
    return result


def selected_modes(mode: str) -> tuple[str, ...]:
    return ("stable", "fresh") if mode == "both" else (mode,)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("stable", "fresh", "both"), default="both")
    parser.add_argument("--count", type=int, default=1, help="number of trials")
    parser.add_argument("--cooldown", type=float, default=30.0, help="seconds between login attempts")
    parser.add_argument("--login-timeout", type=float, default=45.0, help="seconds allowed for each login")
    parser.add_argument(
        "--pairing",
        choices=("separate", "crossover"),
        default="separate",
        help="use separate accounts or test both profiles on each account",
    )
    parser.add_argument("--output", type=Path, default=Path("login-matrix.jsonl"))
    args = parser.parse_args(argv)

    if args.count <= 0:
        parser.error("--count must be positive")
    if args.cooldown < MIN_COOLDOWN_SECONDS:
        parser.error(f"--cooldown must be at least {MIN_COOLDOWN_SECONDS:g} seconds")
    if args.login_timeout <= 0:
        parser.error("--login-timeout must be positive")
    args.attempts = args.count * len(selected_modes(args.mode))
    if args.attempts > MAX_ATTEMPTS:
        parser.error(f"the matrix is limited to {MAX_ATTEMPTS} login attempts")
    return args


def require_opt_in(environ: dict[str, str]) -> str:
    if environ.get("IG_RUN_LOGIN_MATRIX") != "1":
        raise RuntimeError("set IG_RUN_LOGIN_MATRIX=1 to run login experiments")
    url = environ.get("TEST_ACCOUNTS_URL", "").strip()
    if not url:
        raise RuntimeError("TEST_ACCOUNTS_URL is required")
    return url
