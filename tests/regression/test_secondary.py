import base64
import json
import unittest


def literal(value):
    if isinstance(value, dict):
        keys = " ".join(json.dumps(k) for k in value)
        values = " ".join(literal(v) for v in value.values())
        return f"(f4i (dkc {keys}) (dkc {values}))"
    return json.dumps(value)


def envelope(action="", maps=(), embedded=()):
    bundle = {
        "layout": {
            "bloks_payload": {
                "action": action,
                "tree": {"button": " ".join(literal(m) for m in maps)},
                "embedded_payloads": list(embedded),
            }
        }
    }
    return {"data": {"1$bloks_action": {"action": {"action_bundle": {"bloks_bundle_action": json.dumps(bundle)}}}}}


def server(stage, context="opaque-context"):
    value = {
        "reg_context": context,
        "reg_info": json.dumps({"username": "extra_profile"}),
        "flow_info": json.dumps({"flow_name": "secondary_profile_creation_ig_default", "flow_type": "spc"}),
        "device_id": "android-example",
        "family_device_id": "family-example",
        "qe_device_id": "uuid-example",
        "waterfall_id": "waterfall-example",
        "current_step": {"username": 0, "optin": 2, "create": 4}[stage],
        "is_from_logged_out": False,
    }
    value.update(
        {
            "username": {"action": 1},
            "optin": {"is_tds_reg_flow": False},
            "create": {"should_ignore_suma_check": False, "app_id": 0},
        }[stage]
    )
    return value


def success(pk="202", username="extra_profile", user_id=None, auth_override=None):
    auth = {"ds_user_id": pk, "sessionid": "test-session"}
    if auth_override is not None:
        auth = auth_override
    token = "Bearer IGT:2:" + base64.b64encode(json.dumps(auth).encode()).decode()
    wrapper = {
        "registration_response": json.dumps(
            {
                "status": "ok",
                "account_created": True,
                "created_user": {
                    "pk": pk,
                    **({"id": user_id} if user_id is not None else {}),
                    "username": username,
                    "full_name": "",
                    "profile_pic_url": "https://example.com/avatar.jpg",
                },
            }
        ),
        "headers": json.dumps({"ig-set-authorization": token, "ig-set-x-mid": "new-mid"}),
        "cookies": json.dumps({"sessionid": "test-session", "ds_user_id": pk}),
    }
    return envelope(action="(dsh (fom 1 1 " + json.dumps(json.dumps(wrapper)) + "))")


class SecondaryContractTests(unittest.TestCase):
    def helpers(self):
        from aiograpi import secondary

        return secondary

    def test_selects_button_context_not_last_context(self):
        helpers = self.helpers()
        selected = server("username", "next-context")
        other = dict(selected, action=0, reg_context="typing-context")
        result = helpers.continuation(envelope(maps=[selected, other]), "username")
        self.assertEqual(result["reg_context"], "next-context")
        self.assertEqual(result["is_from_logged_out"], 0)

    def test_duplicate_literal_maps_and_nested_network_data(self):
        helpers = self.helpers()
        value = server("optin")
        value["si_device_param_network_info"] = {"is_wifi": True, "default_subscription_info": {"sim_count": 1}}
        result = helpers.continuation(envelope(maps=[value, value]), "optin")
        self.assertEqual(result["si_device_param_network_info"]["is_wifi"], 1)

    def test_conflicting_continuations_are_rejected(self):
        helpers = self.helpers()
        with self.assertRaises(ValueError):
            helpers.continuation(envelope(maps=[server("username", "a"), server("username", "b")]), "username")

    def test_missing_wrong_flow_and_nonliteral_maps_are_rejected(self):
        helpers = self.helpers()
        for response in [
            envelope(),
            envelope(maps=[dict(server("create"), flow_info="{}")]),
            envelope(action='(f4i (dkc "reg_context") (dkc (execute "something")))'),
        ]:
            with self.subTest(response=str(response)[:20]), self.assertRaises(ValueError):
                helpers.continuation(response, "create")

    def test_embedded_registration_headers_are_paired_with_user(self):
        helpers = self.helpers()
        user, auth, headers, cookies = helpers.registration(success(), "101", "extra_profile")
        self.assertEqual(str(user["pk"]), "202")
        self.assertEqual(auth["ds_user_id"], "202")
        self.assertEqual(headers["ig-set-x-mid"], "new-mid")
        self.assertEqual(cookies["sessionid"], auth["sessionid"])

    def test_rejects_parent_identity_and_wrong_username(self):
        helpers = self.helpers()
        for response in [success(pk="101"), success(username="somebody_else")]:
            with self.subTest(response=str(response)[:20]), self.assertRaises(ValueError):
                helpers.registration(response, "101", "extra_profile")

    def test_rejects_conflicting_id_and_pk(self):
        with self.assertRaises(ValueError):
            self.helpers().registration(success(user_id="101"), "101", "extra_profile")

    def test_rejects_invalid_authorization_identity_or_session(self):
        for auth in [
            {},
            {"ds_user_id": "101", "sessionid": "test"},
            {"ds_user_id": "202", "sessionid": ""},
            {"ds_user_id": "202", "sessionid": 123},
        ]:
            with self.subTest(auth=auth), self.assertRaises(ValueError):
                self.helpers().registration(success(auth_override=auth), "101", "extra_profile")

    def test_does_not_accept_success_from_embedded_unexecuted_template(self):
        helpers = self.helpers()
        with self.assertRaises(ValueError):
            helpers.registration(envelope(embedded=[success()]), "101", "extra_profile")

    def test_parenthesis_ui_label_is_not_an_action(self):
        helpers = self.helpers()
        response = envelope(maps=[server("username")])
        response["ui_label"] = "("
        self.assertEqual(helpers.continuation(response, "username")["action"], 1)

    def test_rejects_excessive_payload(self):
        helpers = self.helpers()
        with self.assertRaises(ValueError):
            helpers.continuation({"data": "x" * 2_000_001}, "username")


class SecondaryFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from aiograpi import Client

        self.parent = Client(
            settings={
                "authorization_data": {"ds_user_id": "101", "sessionid": "parent-session"},
                "cookies": {"sessionid": "parent-session", "ds_user_id": "101"},
            },
            proxy="http://127.0.0.1:12345",
            private_transport="requests",
        )
        self.parent.request_timeout = 0
        self.before = json.dumps(self.parent.get_settings(), sort_keys=True)
        self.calls = []
        self.http_clients = []

    async def asyncTearDown(self):
        import asyncio

        await asyncio.gather(
            *(s._client.aclose() for s in [self.parent.private, self.parent.public, self.parent.graphql])
        )

    def transport(self, fail_at=None, redirect=False, cancel=False):
        import asyncio
        from urllib.parse import parse_qs

        import httpx

        test = self
        replies = [
            envelope(maps=[server("username")]),
            envelope(maps=[server("optin")]),
            envelope(maps=[server("create")]),
            success(),
        ]

        async def send(client, request):
            test.http_clients.append(client)
            form = parse_qs((await request.aread()).decode())
            variables = json.loads(form["variables"][0])
            test.calls.append((request, variables))
            index = len(test.calls) - 1
            if index == fail_at:
                if cancel:
                    raise asyncio.CancelledError()
                if redirect:
                    return httpx.Response(307, headers={"location": "https://example.com/redirect"}, request=request)
                raise httpx.ReadTimeout("request failed", request=request)
            return httpx.Response(200, json=replies[index], request=request)

        return send

    async def test_isolated_session_and_embedded_credentials(self):
        from unittest.mock import patch

        with patch("httpx.AsyncClient._send_single_request", self.transport()):
            result = await self.parent.create_secondary_account("extra_profile")
        self.assertEqual(result.user.pk, "202")
        self.assertEqual(result.settings["authorization_data"]["ds_user_id"], "202")
        self.assertEqual(result.settings["cookies"]["sessionid"], "test-session")
        self.assertNotIn("test-session", repr(result))
        self.assertEqual(json.dumps(self.parent.get_settings(), sort_keys=True), self.before)
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(all(c.is_closed for c in self.http_clients))
        for request, variables in self.calls:
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("cookie", request.headers)
            self.assertNotIn("ig-u-ds-user-id", request.headers)
            self.assertEqual(request.url.host, "b.i.instagram.com")
        entry = json.loads(self.calls[0][1]["params"]["params"])
        self.assertEqual(entry["auth_token"], self.parent.authorization)
        self.assertEqual(json.loads(entry["flow_info"])["flow_type"], "spc")
        self.assertNotIn("parent-session", json.dumps(result.settings))
        from aiograpi import Client

        additional = Client(settings=result.settings, proxy=self.parent.proxy)
        try:
            self.assertEqual(str(additional.user_id), "202")
            self.assertEqual(additional.sessionid, "test-session")
            self.assertEqual(additional.proxy, self.parent.proxy)
            self.assertEqual(additional.tls_verify, self.parent.tls_verify)
        finally:
            for session in (additional.private, additional.public, additional.graphql):
                await session._client.aclose()

    async def test_create_timeout_is_not_retried_and_reports_unknown_outcome(self):
        from unittest.mock import patch

        from aiograpi.exceptions import SecondaryAccountError

        with patch("httpx.AsyncClient._send_single_request", self.transport(fail_at=3)):
            with self.assertRaises(SecondaryAccountError) as raised:
                await self.parent.create_secondary_account("extra_profile")
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(raised.exception.stage, "create")
        self.assertTrue(raised.exception.creation_may_have_succeeded)
        self.assertTrue(all(c.is_closed for c in self.http_clients))
        self.assertEqual(json.dumps(self.parent.get_settings(), sort_keys=True), self.before)

    async def test_creation_redirect_is_not_followed(self):
        from unittest.mock import patch

        from aiograpi.exceptions import SecondaryAccountError

        with patch("httpx.AsyncClient._send_single_request", self.transport(fail_at=3, redirect=True)):
            with self.assertRaises(SecondaryAccountError):
                await self.parent.create_secondary_account("extra_profile")
        self.assertEqual(len(self.calls), 4)

    async def test_cancellation_closes_temporary_session(self):
        import asyncio
        from unittest.mock import patch

        with patch("httpx.AsyncClient._send_single_request", self.transport(fail_at=1, cancel=True)):
            with self.assertRaises(asyncio.CancelledError):
                await self.parent.create_secondary_account("extra_profile")
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(c.is_closed for c in self.http_clients))
        self.assertEqual(json.dumps(self.parent.get_settings(), sort_keys=True), self.before)

    async def test_rejects_invalid_input_before_network(self):
        from unittest.mock import patch

        with patch("httpx.AsyncClient._send_single_request", self.transport()):
            for username in ["", "with space", "x" * 31, "name\n", "name/other"]:
                with self.subTest(username=username), self.assertRaises(ValueError):
                    await self.parent.create_secondary_account(username)
            with self.assertRaises(ValueError):
                await self.parent.create_secondary_account("extra_profile", link_to_main_account=False)
        self.assertEqual(self.calls, [])

    async def test_cleanup_failure_still_closes_other_clients_and_reports_stage(self):
        from unittest.mock import patch

        import httpx

        from aiograpi.exceptions import SecondaryAccountError

        original_close = httpx.AsyncClient.aclose
        closed = []

        async def close(client):
            await original_close(client)
            closed.append(client)
            if len(self.calls) == 4 and sum(c in self.http_clients for c in closed) == 1:
                raise RuntimeError("sensitive cleanup detail")

        with (
            patch("httpx.AsyncClient._send_single_request", self.transport()),
            patch("httpx.AsyncClient.aclose", close),
        ):
            with self.assertRaises(SecondaryAccountError) as raised:
                await self.parent.create_secondary_account("extra_profile")
        self.assertEqual(raised.exception.stage, "cleanup")
        self.assertTrue(raised.exception.creation_may_have_succeeded)
        self.assertNotIn("sensitive", str(raised.exception))
        self.assertGreaterEqual(len(closed), 3)

    async def test_repeated_cancellation_during_each_cleanup_phase_drains_clients(self):
        import asyncio
        from unittest.mock import patch

        import httpx

        from aiograpi.httpx_ext import Session

        original_retired = Session._close_retired_clients
        original_close = httpx.AsyncClient.aclose
        for phase in ("retired", "active"):
            for request_cancelled in (False, True):
                with self.subTest(phase=phase, request_cancelled=request_cancelled):
                    self.calls = []
                    entered = asyncio.Event()
                    release = asyncio.Event()
                    sessions = []
                    calls_before_cleanup = 2 if request_cancelled else 4

                    async def retired(session):
                        if len(self.calls) == calls_before_cleanup:
                            sessions.append(session)
                            if phase == "retired":
                                entered.set()
                                await release.wait()
                        await original_retired(session)

                    async def close(client):
                        if len(self.calls) == calls_before_cleanup and phase == "active":
                            entered.set()
                            await release.wait()
                        await original_close(client)

                    with (
                        patch(
                            "httpx.AsyncClient._send_single_request",
                            self.transport(fail_at=1 if request_cancelled else None, cancel=request_cancelled),
                        ),
                        patch.object(Session, "_close_retired_clients", retired),
                        patch.object(httpx.AsyncClient, "aclose", close),
                    ):
                        task = asyncio.create_task(self.parent.create_secondary_account("extra_profile"))
                        try:
                            await asyncio.wait_for(entered.wait(), timeout=2)
                            task.cancel()
                            await asyncio.sleep(0)
                            task.cancel()
                            await asyncio.sleep(0)
                            self.assertFalse(task.done(), "Cancellation abandoned connection cleanup")
                        finally:
                            release.set()
                            with self.assertRaises(asyncio.CancelledError):
                                await task
                    self.assertEqual(len(sessions), 3)
                    self.assertTrue(all(s._client.is_closed and not s._retired_clients for s in sessions))
