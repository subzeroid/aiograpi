import unittest
from unittest.mock import AsyncMock, Mock

import orjson

from aiograpi import Client
from aiograpi.exceptions import ClientLoginRequired


class PublicRequestRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_public_request_maps_challenge_redirect_html_to_login_required(self):
        client = Client()
        client.last_response_ts = 0
        response = Mock()
        response.status_code = 200
        response.url = "https://www.instagram.com/challenge/?next=/graphql/query/"
        response.text = '<!DOCTYPE html><html lang="en" class="no-js logged-in client-root"></html>'
        response.raise_for_status.return_value = None
        response.json.side_effect = orjson.JSONDecodeError("unexpected character", response.text, 0)
        client.public.get = AsyncMock(return_value=response)

        with self.assertRaises(ClientLoginRequired):
            await client._send_public_request("https://www.instagram.com/graphql/query/", return_json=True)

    async def test_public_doc_id_graphql_request_injects_logged_in_public_cookies(self):
        client = Client()
        client.authorization_data = {"sessionid": "123:session", "ds_user_id": "123"}
        client.public.set_cookies({"csrftoken": "csrf-token"})
        client.public_request = AsyncMock(return_value={"data": {"ok": True}})

        result = await client.public_doc_id_graphql_request("doc-id", {"shortcode": "abc"})

        self.assertEqual(result, {"ok": True})
        self.assertEqual(client.public.cookies_dict()["sessionid"], "123:session")
        headers = client.public_request.await_args.kwargs["headers"]
        self.assertEqual(headers["X-CSRFToken"], "csrf-token")
