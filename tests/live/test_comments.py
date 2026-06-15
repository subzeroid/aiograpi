import unittest

from aiograpi import Client
from aiograpi.exceptions import (
    ClientForbiddenError,
    ClientGraphqlError,
    ClientLoginRequired,
    ClientThrottledError,
    ClientUnauthorizedError,
)


class ClientPublicCommentLiveTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_media_comments_public_gql_live(self):
        code = "C_BM2yAN4Rm"
        transports = ["requests"]
        try:
            import curl_adapter  # noqa: F401
        except ImportError:
            pass
        else:
            transports.append("curl")

        errors = []
        for transport in transports:
            client = Client(public_transport=transport, request_timeout=0, public_request_retries_count=1)
            try:
                comments = await client.media_comments_public_gql(code, amount=3, max_requests=1)
            except (
                ClientForbiddenError,
                ClientGraphqlError,
                ClientLoginRequired,
                ClientThrottledError,
                ClientUnauthorizedError,
            ) as exc:
                errors.append(f"{transport}: {exc.__class__.__name__}")
                continue
            break
        else:
            self.skipTest("Instagram public comments endpoint is gated: " + "; ".join(errors))

        self.assertTrue(comments)
        self.assertLessEqual(len(comments), 3)
        self.assertTrue(comments[0].get("id") or comments[0].get("pk"))
        self.assertTrue(comments[0].get("text"))
