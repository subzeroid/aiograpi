import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "research_login_matrix.py"
SPEC = importlib.util.spec_from_file_location("research_login_matrix", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
login_matrix = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = login_matrix
SPEC.loader.exec_module(login_matrix)


def test_build_accounts_url_preserves_query_and_sets_count():
    assert login_matrix.build_accounts_url("https://pool.test/accounts?kind=live", 3) == (
        "https://pool.test/accounts?kind=live&count=3"
    )
    assert login_matrix.build_accounts_url("https://pool.test/accounts?count=99", 2) == (
        "https://pool.test/accounts?count=2"
    )


def test_device_only_settings_drops_authentication_state():
    assert login_matrix.device_only_settings(
        {
            "uuids": {"phone_id": "phone"},
            "device_settings": {"model": "Pixel"},
            "sessionid": "secret",
            "authorization_data": {"sessionid": "secret"},
            "totp_seed": "secret",
        }
    ) == {
        "uuids": {"phone_id": "phone"},
        "device_settings": {"model": "Pixel"},
    }


def test_build_jobs_uses_separate_accounts_and_alternates_order():
    accounts = [{"username": f"u{index}", "password": "p"} for index in range(4)]

    jobs = login_matrix.build_jobs(accounts, ("stable", "fresh"), "separate", 2)

    assert [(job.trial, job.account_index, job.mode) for job in jobs] == [
        (0, 0, "stable"),
        (0, 1, "fresh"),
        (1, 2, "fresh"),
        (1, 3, "stable"),
    ]


def test_build_jobs_crossover_reuses_one_account_per_trial():
    accounts = [{"username": f"u{index}", "password": "p"} for index in range(2)]

    jobs = login_matrix.build_jobs(accounts, ("stable", "fresh"), "crossover", 2)

    assert [(job.trial, job.account_index, job.mode) for job in jobs] == [
        (0, 0, "stable"),
        (0, 0, "fresh"),
        (1, 1, "fresh"),
        (1, 1, "stable"),
    ]


def test_build_jobs_rejects_incomplete_account_pool_without_echoing_records():
    with pytest.raises(ValueError, match="need 2 accounts; endpoint returned 1") as exc_info:
        login_matrix.build_jobs(
            [{"username": "private-name", "password": "secret"}], ("stable", "fresh"), "separate", 1
        )

    assert "private-name" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_profile_digest_is_stable_only_within_one_run():
    first = login_matrix.digest_profile_value(b"run-key", "device-id")

    assert first == login_matrix.digest_profile_value(b"run-key", "device-id")
    assert first != login_matrix.digest_profile_value(b"other-key", "device-id")
    assert "device-id" not in first
    assert len(first) == 16


@pytest.mark.parametrize(
    "argv",
    [
        ["--count", "0"],
        ["--count", "-1"],
        ["--login-timeout", "0"],
        ["--cooldown", "9.99"],
        ["--mode", "both", "--count", "6"],
        ["--mode", "stable", "--count", "11"],
    ],
)
def test_parse_args_rejects_unsafe_bounds(argv):
    with pytest.raises(SystemExit):
        login_matrix.parse_args(argv)


def test_parse_args_accepts_at_most_ten_attempts():
    both = login_matrix.parse_args(["--mode", "both", "--count", "5"])
    single = login_matrix.parse_args(["--mode", "stable", "--count", "10"])

    assert both.attempts == 10
    assert single.attempts == 10
    assert both.cooldown == 30.0


def test_require_opt_in_needs_gate_and_account_pool_url():
    with pytest.raises(RuntimeError, match="IG_RUN_LOGIN_MATRIX=1"):
        login_matrix.require_opt_in({"TEST_ACCOUNTS_URL": "https://pool.test/accounts"})
    with pytest.raises(RuntimeError, match="TEST_ACCOUNTS_URL"):
        login_matrix.require_opt_in({"IG_RUN_LOGIN_MATRIX": "1"})

    assert (
        login_matrix.require_opt_in(
            {
                "IG_RUN_LOGIN_MATRIX": "1",
                "TEST_ACCOUNTS_URL": "https://pool.test/accounts",
            }
        )
        == "https://pool.test/accounts"
    )
