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

    async def test_public_doc_id_graphql_request_posts_web_api_with_lsd(self):
        client = Client()
        client.public.set_cookies({"csrftoken": "csrf-token"})
        html = '<html><script>["LSD",[],{"token":"lsd-token"}]</script></html>'
        client.public_request = AsyncMock(side_effect=[html, {"data": {"ok": True}}])

        result = await client.public_doc_id_graphql_request(
            "27128499623469141",
            {"shortcode": "DaHEdwgogl4"},
            referer="https://www.instagram.com/p/DaHEdwgogl4/",
            url=client.GRAPHQL_PUBLIC_WEB_API_URL,
            include_lsd=True,
            headers={"X-FB-Friendly-Name": "PolarisPostRootQuery"},
        )

        self.assertEqual(result, {"ok": True})
        bootstrap_call, query_call = client.public_request.await_args_list
        self.assertEqual(bootstrap_call.args[0], "https://www.instagram.com/p/DaHEdwgogl4/")
        self.assertFalse(bootstrap_call.kwargs["return_json"])
        self.assertEqual(query_call.args[0], client.GRAPHQL_PUBLIC_WEB_API_URL)
        kwargs = query_call.kwargs
        self.assertEqual(kwargs["data"]["doc_id"], "27128499623469141")
        self.assertEqual(kwargs["data"]["variables"], '{"shortcode":"DaHEdwgogl4"}')
        self.assertEqual(kwargs["data"]["lsd"], "lsd-token")
        self.assertEqual(kwargs["headers"]["X-FB-LSD"], "lsd-token")
        self.assertEqual(kwargs["headers"]["X-CSRFToken"], "csrf-token")
        self.assertEqual(kwargs["headers"]["X-FB-Friendly-Name"], "PolarisPostRootQuery")
        self.assertEqual(kwargs["headers"]["X-ASBD-ID"], "129477")
        self.assertEqual(kwargs["headers"]["X-IG-App-ID"], "936619743392459")
        self.assertFalse(kwargs["update_headers"])
        self.assertTrue(kwargs["return_json"])
