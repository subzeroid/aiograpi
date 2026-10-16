# Value: protects=exact HTTP 400 needs_upgrade classification and its public diagnostics;
# fails_when=generic, broad, or reordered classification loses the original failure;
# why_new=existing login tests only see generic errors; seam=none
"""Exercise needs_upgrade classification through the HTTPX transport boundary."""

import asyncio

import httpx
import pytest

from aiograpi import Client, exceptions


def classify(payload, status=400, endpoint="accounts/login/"):
    async def request_failure():
        client = Client(private_transport="requests", settings={"session_retry_total": 0, "request_timeout": 0})
        responses = []

        def handle(request):
            assert not responses, "Classification must not resend the request"
            assert str(request.url) == f"https://i.instagram.com/api/v1/{endpoint}"
            response = httpx.Response(status, json=payload)
            responses.append(response)
            return response

        client.private._client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        try:
            with pytest.raises(exceptions.ClientError) as raised:
                await client._send_private_request(endpoint, login=True)
        finally:
            await client.private._close()
        assert len(responses) == 1
        assert client.last_response is responses[0]
        return client, responses[0], raised.value

    return asyncio.run(request_failure())


@pytest.mark.parametrize("extra", [{}, {"response": {}, "code": 999}])
def test_http400_needs_upgrade_has_typed_original_diagnostics(extra):
    payload = {
        "status": "fail",
        "error_type": "needs_upgrade",
        "message": "Your version of Instagram is out of date. 🚧",
        **extra,
    }

    client, response, error = classify(payload)

    # Keep baseline collection working so RED reports the actual generic error.
    assert type(error).__name__ == "ClientNeedsUpgradeError"
    assert type(error) is exceptions.ClientNeedsUpgradeError
    assert isinstance(error, exceptions.UnknownError)
    assert error.response is response
    assert error.code == 400
    assert error.message == payload["message"]
    assert str(error) == payload["message"]
    assert error.error_type == "needs_upgrade"
    assert client.last_json == payload


@pytest.mark.parametrize("flag", [None, "", "temporary_error", "NEEDS_UPGRADE", " needs_upgrade", "needs_upgrade "])
def test_other_flags_remain_unknown_error(flag):
    payload = {"status": "fail", "message": "needs_upgrade", "error_type": flag}

    client, _, error = classify(payload)

    assert type(error) is exceptions.UnknownError
    assert client.last_json == payload


@pytest.mark.parametrize(
    ("endpoint", "extra", "expected"),
    [
        ("accounts/login/", {"message": "challenge_required", "challenge": {}}, exceptions.ChallengeRequired),
        ("accounts/login/", {"two_factor_info": {"two_factor_identifier": "synthetic"}}, exceptions.TwoFactorRequired),
        ("accounts/login/", {"message": "feedback_required"}, exceptions.FeedbackRequired),
        (
            "accounts/login/",
            {"message": "Please wait a few minutes before you try again"},
            exceptions.PleaseWaitFewMinutes,
        ),
        (
            "accounts/edit_profile/",
            {"message": "You need an email or confirmed phone number."},
            exceptions.AccountContactPointRequired,
        ),
        ("accounts/edit_profile/", {}, exceptions.AccountEditError),
        (
            "direct_v2/threads/broadcast/text/",
            {"message": "You can't message this account unless they follow you."},
            exceptions.DirectMessageRequestsDisabled,
        ),
        ("media/123/info/", {"message": "Media is unavailable"}, exceptions.MediaUnavailable),
    ],
)
def test_higher_priority_failures_keep_their_classification(endpoint, extra, expected):
    payload = {"status": "fail", "error_type": "needs_upgrade", "message": "Upgrade requested", **extra}

    _, _, error = classify(payload, endpoint=endpoint)

    assert type(error) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (200, exceptions.ClientStatusFail),
        (401, exceptions.ClientUnauthorizedError),
        (403, exceptions.ClientForbiddenError),
        (404, exceptions.ClientNotFoundError),
        (408, exceptions.ClientRequestTimeout),
        (429, exceptions.ClientThrottledError),
        (500, exceptions.ClientUnknownError),
    ],
)
def test_other_statuses_keep_their_classification(status, expected):
    payload = {"status": "fail", "error_type": "needs_upgrade", "message": "Upgrade requested"}

    _, _, error = classify(payload, status=status)

    assert type(error) is expected
