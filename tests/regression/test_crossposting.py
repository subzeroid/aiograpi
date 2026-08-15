import unittest
from pathlib import Path
from typing import Literal, Union, get_args, get_origin, get_type_hints
from unittest.mock import AsyncMock, Mock, mock_open, patch

from aiograpi import Client
from aiograpi.exceptions import ClientError, ClientGraphqlError
from aiograpi.extractors import extract_media_v1


class CrossPostingRegressionTestCase(unittest.IsolatedAsyncioTestCase):
    def build_client(self):
        client = Client()
        client.settings = {}
        client._user_id = "1"
        client.uuid = "uuid"
        client.android_device_id = "device"
        client.client_session_id = "client-session"
        client.timezone_offset = 0
        client.last_json = {}
        client.last_response = None
        client.set_device({})
        client.expose = AsyncMock(return_value=None)
        return client

    def assert_fb_destination_type_literal(self, method_name, parameter_name):
        hints = get_type_hints(getattr(Client, method_name))
        annotation = hints[parameter_name]
        self.assertIs(get_origin(annotation), Union)
        self.assertIn(type(None), get_args(annotation))
        literal_args = [arg for arg in get_args(annotation) if get_origin(arg) is Literal]
        self.assertEqual(1, len(literal_args))
        self.assertEqual(("USER", "PAGE"), get_args(literal_args[0]))

    async def test_feed_crossposting_destination_type_annotations_are_literal(self):
        self.assert_fb_destination_type_literal("media_share_to_fb_destination", "destination_type")
        self.assert_fb_destination_type_literal("media_share_to_fb_extra_data", "destination_type")

    async def test_media_share_to_fb_unified_config_requests_android_graphql_www(self):
        client = self.build_client()
        response = {"data": {"xcxp_unified_crossposting_configs_root": {}}}
        client.private_graphql_www_request = AsyncMock(return_value=response)
        client.private_graphql_query_request = AsyncMock()

        result = await client.media_share_to_fb_unified_config()

        client.private_graphql_query_request.assert_not_awaited()
        client.private_graphql_www_request.assert_awaited_once_with(
            friendly_name="CrosspostingUnifiedConfigsQuery",
            variables={
                "configs_request": {
                    "source_app": "IG",
                    "crosspost_app_surface_list": [
                        {
                            "source_surface": "STORY",
                            "destination_app": "FB",
                            "destination_surface": "STORY",
                        },
                        {
                            "source_surface": "FEED",
                            "destination_app": "FB",
                            "destination_surface": "FEED",
                        },
                        {
                            "source_surface": "REELS",
                            "destination_app": "FB",
                            "destination_surface": "REELS",
                        },
                    ],
                }
            },
            client_doc_id="216179630714134719310007237117",
            domain="i.instagram.com",
            extra_headers={
                "Priority": "u=3, i",
                "X-FB-RMD": "state=URL_ELIGIBLE",
                "X-Root-Field-Name": "xcxp_unified_crossposting_configs_root",
            },
            purpose=None,
        )
        self.assertEqual(
            result,
            {
                "data": {"xcxp_unified_crossposting_configs_root": {}},
                "status": "ok",
            },
        )

    async def test_media_share_to_fb_connected_services_config_requests_android_fx_query(self):
        client = self.build_client()
        response = {"data": {"fx_service_cache": {"services": []}}}
        client.private_graphql_www_request = AsyncMock(return_value=response)

        result = await client.media_share_to_fb_connected_services_config()

        client.private_graphql_www_request.assert_awaited_once_with(
            friendly_name="FxIgConnectedServicesInfoQuery",
            variables={
                "service_names": ["CROSS_POSTING_SETTING"],
                "custom_partner_params": [
                    {"value": "FB", "key": "CROSSPOSTING_DESTINATION_APP"},
                    {"value": "", "key": "CROSSPOSTING_SHARE_TO_SURFACE"},
                    {
                        "value": "true",
                        "key": "OVERRIDE_USER_VALIDATION_WITH_CXP_ELIGIBILITY_RULE",
                    },
                ],
                "client_caller_name": "ig_android_service_cache_crossposting_setting",
                "caller_name": "fx_product_foundation_client_FXOnline_client_cache",
            },
            client_doc_id="21631519911413744205623093060",
            domain="i.instagram.com",
            extra_headers={
                "Priority": "u=3, i",
                "X-FB-RMD": "state=URL_ELIGIBLE",
                "X-Root-Field-Name": "fx_service_cache",
            },
            purpose=None,
        )
        self.assertEqual(
            result,
            {
                "data": {"fx_service_cache": {"services": []}},
                "status": "ok",
            },
        )

    async def test_media_share_to_fb_destination_falls_back_to_connected_services_identity(self):
        client = self.build_client()
        unified_config = {
            "data": {"xcxp_unified_crossposting_configs_root": {"configs": []}},
            "status": "ok",
        }
        connected_services_config = {
            "data": {
                "1$fx_service_cache(caller_name:$caller_name)": {
                    "services": [
                        {
                            "identity_mapping": [
                                {
                                    "destination_identities": [
                                        {
                                            "obfuscated_identity_id": "feed-service-destination",
                                            "identity_type": "FB_USER",
                                            "surface_to_xpost_eligibilities": [
                                                {"surface": "FEED", "is_eligible": True},
                                                {"surface": "REELS", "is_eligible": False},
                                            ],
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            },
            "status": "ok",
        }
        client.media_share_to_fb_unified_config = AsyncMock(return_value=unified_config)
        client.media_share_to_fb_connected_services_config = AsyncMock(return_value=connected_services_config)

        destination = await client.media_share_to_fb_destination()

        self.assertEqual(client.media_share_to_fb_unified_config.await_count, 2)
        client.media_share_to_fb_connected_services_config.assert_awaited_once_with()
        self.assertEqual(
            destination,
            {
                "destination_id": "feed-service-destination",
                "destination_type": "USER",
            },
        )

    async def test_media_share_to_fb_destination_selects_feed_and_normalizes_identity_type(self):
        client = self.build_client()
        config = {
            "data": {
                "xcxp_unified_crossposting_configs_root": {
                    "configs": [
                        {
                            "source_surface": "REELS",
                            "destination_app": "FB",
                            "destination_surface": "REELS",
                            "destination": {
                                "destination_id": "reels-destination",
                                "destination_type": "USER",
                            },
                        },
                        {
                            "source_surface": "FEED",
                            "destination_app": "FB",
                            "destination_surface": "FEED",
                            "destination": {
                                "obfuscated_identity_id": "feed-destination",
                                "identity_type": "FB_PAGE",
                            },
                        },
                    ]
                }
            }
        }

        destination = await client.media_share_to_fb_destination(config=config)

        self.assertEqual(
            destination,
            {
                "destination_id": "feed-destination",
                "destination_type": "PAGE",
            },
        )

    async def test_media_share_to_fb_destination_applies_partial_type_override_to_unified_identity(self):
        client = self.build_client()
        config = {
            "data": {
                "xcxp_unified_crossposting_configs_root": {
                    "configs": [
                        {
                            "source_surface": "FEED",
                            "destination_app": "FB",
                            "destination_surface": "FEED",
                            "destination": {
                                "destination_id": "feed-destination",
                                "destination_type": "USER",
                            },
                        }
                    ]
                }
            }
        }

        destination = await client.media_share_to_fb_destination(
            config=config,
            destination_type="PAGE",
        )

        self.assertEqual(
            destination,
            {
                "destination_id": "feed-destination",
                "destination_type": "PAGE",
            },
        )

    async def test_media_share_to_fb_unified_destination_stops_after_first_successful_query(self):
        client = self.build_client()
        client.media_share_to_fb_unified_config = AsyncMock(
            return_value={
                "data": {
                    "xcxp_unified_crossposting_configs_root": {
                        "configs": [
                            {
                                "source_surface": "FEED",
                                "destination_app": "FB",
                                "destination_surface": "FEED",
                                "destination": {
                                    "destination_id": "feed-destination",
                                    "destination_type": "USER",
                                },
                            }
                        ]
                    }
                }
            }
        )

        destination = await client.media_share_to_fb_unified_destination()

        self.assertEqual(destination["destination_id"], "feed-destination")
        client.media_share_to_fb_unified_config.assert_awaited_once_with()

    async def test_media_share_to_fb_destination_extracts_feed_service_identity_mapping(self):
        client = self.build_client()
        config = {
            "data": {
                "fx_service_cache": {
                    "services": [
                        {
                            "custom_service_data": {
                                "auto_xpost_setting": [
                                    {
                                        "is_auto_crosspost_enabled": True,
                                        "source_surface": "STORY",
                                    },
                                    {
                                        "is_auto_crosspost_enabled": True,
                                        "source_surface": "FEED",
                                    },
                                ]
                            },
                            "identity_mapping": [
                                {
                                    "destination_identities": [
                                        {
                                            "obfuscated_identity_id": "feed-service-destination",
                                            "identity_type": "FB_USER",
                                        }
                                    ]
                                }
                            ],
                        }
                    ]
                }
            }
        }

        destination = await client.media_share_to_fb_destination(config=config)

        self.assertEqual(
            destination,
            {
                "destination_id": "feed-service-destination",
                "destination_type": "USER",
            },
        )

    async def test_media_share_to_fb_destination_rejects_ineligible_connected_service_identity(self):
        client = self.build_client()
        config = {
            "data": {
                "fx_service_cache": {
                    "services": [
                        {
                            "custom_service_data": {
                                "auto_xpost_setting": [
                                    {
                                        "is_auto_crosspost_enabled": True,
                                        "source_surface": "FEED",
                                    }
                                ]
                            },
                            "identity_mapping": [
                                {
                                    "destination_identities": [
                                        {
                                            "obfuscated_identity_id": "ineligible-feed-destination",
                                            "identity_type": "FB_USER",
                                            "surface_to_xpost_eligibilities": [
                                                {
                                                    "surface": "FEED",
                                                    "is_eligible": False,
                                                }
                                            ],
                                        }
                                    ]
                                }
                            ],
                        }
                    ]
                }
            }
        }

        with self.assertRaises(ClientError):
            await client.media_share_to_fb_destination(config=config)

    async def test_media_share_to_fb_destination_applies_partial_id_override_to_connected_service_identity(self):
        client = self.build_client()
        config = {
            "data": {
                "fx_service_cache": {
                    "services": [
                        {
                            "identity_mapping": [
                                {
                                    "destination_identities": [
                                        {
                                            "obfuscated_identity_id": "service-destination",
                                            "identity_type": "FB_USER",
                                            "surface_to_xpost_eligibilities": [
                                                {"surface": "FEED", "is_eligible": True}
                                            ],
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        }

        destination = await client.media_share_to_fb_destination(
            config=config,
            destination_id="override-destination",
        )

        self.assertEqual(
            destination,
            {
                "destination_id": "override-destination",
                "destination_type": "USER",
            },
        )

    async def test_media_share_to_fb_extra_data_builds_feed_crosspost_payload(self):
        client = self.build_client()

        extra_data = await client.media_share_to_fb_extra_data(
            destination_id="fb-destination",
            destination_type="USER",
            validation_bypass=["AUTO_CROSSPOST_SETTING"],
            attempt_id="attempt-id",
        )

        self.assertEqual(
            extra_data,
            {
                "share_to_facebook": "1",
                "share_to_fb_destination_id": "fb-destination",
                "share_to_fb_destination_type": "USER",
                "share_to_facebook_validation_bypass": ["AUTO_CROSSPOST_SETTING"],
                "no_token_crosspost": "1",
                "attempt_id": "attempt-id",
            },
        )

    async def test_media_share_to_threads_config_requests_linked_profile_query(self):
        client = self.build_client()
        response = {
            "data": {
                "xcxp_fetch_linked_threads_profile": {
                    "id": "threads-destination",
                    "username": "threads-user",
                }
            }
        }
        client.private_graphql_www_request = AsyncMock(return_value=response)
        client.private_graphql_query_request = AsyncMock()

        result = await client.media_share_to_threads_config()

        client.private_graphql_query_request.assert_not_awaited()
        client.private_graphql_www_request.assert_awaited_once_with(
            friendly_name="LinkedBarcelonaProfileQuery",
            variables={},
            client_doc_id="1294688273527445410149299611",
            domain="i.instagram.com",
            extra_headers={
                "Priority": "u=3, i",
                "X-FB-RMD": "state=URL_ELIGIBLE",
                "X-Root-Field-Name": "xcxp_fetch_linked_threads_profile",
            },
            purpose=None,
        )
        self.assertEqual(
            result,
            {
                "data": {
                    "xcxp_fetch_linked_threads_profile": {
                        "id": "threads-destination",
                        "username": "threads-user",
                    }
                },
                "status": "ok",
            },
        )

    async def test_media_share_to_threads_config_falls_back_when_graphql_www_rejects_unlinked_account(self):
        client = self.build_client()
        response = {"data": {"xcxp_fetch_linked_threads_profile": None}, "status": "ok"}
        client.private_graphql_www_request = AsyncMock(
            side_effect=ClientGraphqlError("GraphQL rejected the unlinked profile query")
        )
        client.private_graphql_query_request = AsyncMock(return_value=response)

        result = await client.media_share_to_threads_config()

        client.private_graphql_www_request.assert_awaited_once()
        client.private_graphql_query_request.assert_awaited_once_with(
            friendly_name="LinkedBarcelonaProfileQuery",
            root_field_name="xcxp_fetch_linked_threads_profile",
            variables={},
            client_doc_id="1294688273527445410149299611",
            priority="u=3, i",
            extra_headers={"X-FB-RMD": "state=URL_ELIGIBLE"},
        )
        self.assertEqual(result, response)

    async def test_media_share_to_threads_destination_extracts_linked_profile_id(self):
        client = self.build_client()

        destination = await client.media_share_to_threads_destination(
            config={
                "data": {
                    "xcxp_fetch_linked_threads_profile": {
                        "id": "threads-destination",
                        "username": "threads-user",
                        "profile_pic_url": "https://example.com/threads.jpg",
                    }
                }
            }
        )

        self.assertEqual(
            destination,
            {
                "destination_id": "threads-destination",
                "username": "threads-user",
                "profile_pic_url": "https://example.com/threads.jpg",
            },
        )

    async def test_media_share_to_threads_destination_rejects_unlinked_profile(self):
        client = self.build_client()

        with self.assertRaises(ClientError) as ctx:
            await client.media_share_to_threads_destination(
                config={"data": {"xcxp_fetch_linked_threads_profile": None}}
            )

        self.assertIn("no linked Threads profile", str(ctx.exception))

    async def test_media_share_to_threads_extra_data_builds_android_payload(self):
        client = self.build_client()

        extra_data = await client.media_share_to_threads_extra_data(
            destination_id="threads-destination",
            validation_bypass=["AUTO_CROSSPOST_SETTING"],
        )

        self.assertEqual(
            extra_data,
            {
                "share_to_threads": "1",
                "share_to_threads_destination_id": "threads-destination",
                "share_to_threads_validation_bypass": ["AUTO_CROSSPOST_SETTING"],
            },
        )

    async def test_media_crossposting_extra_data_combines_destinations_without_mutating_input(self):
        client = self.build_client()
        original = {"disable_comments": 1, "attempt_id": "caller-attempt"}
        client.media_share_to_fb_extra_data = AsyncMock(
            return_value={"share_to_facebook": "1", "attempt_id": "generated-attempt"}
        )
        client.media_share_to_threads_extra_data = AsyncMock(
            return_value={
                "share_to_threads": "1",
                "share_to_threads_destination_id": "threads-destination",
            }
        )

        result = await client._media_crossposting_extra_data(
            original,
            share_to_facebook=True,
            share_to_threads=True,
            fb_destination_id="fb-destination",
            fb_destination_type="PAGE",
            threads_destination_id="threads-destination",
        )

        self.assertEqual(original, {"disable_comments": 1, "attempt_id": "caller-attempt"})
        self.assertEqual(
            result,
            {
                "share_to_facebook": "1",
                "share_to_threads": "1",
                "share_to_threads_destination_id": "threads-destination",
                "disable_comments": 1,
                "attempt_id": "caller-attempt",
            },
        )
        client.media_share_to_fb_extra_data.assert_awaited_once_with(
            destination_id="fb-destination",
            destination_type="PAGE",
            validation_bypass=None,
        )
        client.media_share_to_threads_extra_data.assert_awaited_once_with(
            destination_id="threads-destination",
            validation_bypass=None,
        )

    async def test_extract_media_preserves_crosspost_metadata(self):
        payload = {
            "pk": "1",
            "id": "1_1",
            "code": "abc",
            "taken_at": 1710000000,
            "media_type": 1,
            "caption": {"text": "caption"},
            "user": {
                "pk": "1",
                "username": "example",
                "profile_pic_url": "https://example.com/profile.jpg",
            },
            "like_count": 0,
            "image_versions2": {
                "candidates": [
                    {
                        "url": "https://example.com/photo.jpg",
                        "width": 720,
                        "height": 720,
                    }
                ]
            },
            "crosspost": ["FB", "IG", "THREADS"],
            "crosspost_metadata": {
                "fb_crosspost_fbid": "fb-media-id",
                "threads_crosspost_id": "threads-media-id",
            },
            "has_shared_to_fb": 3,
        }

        media = extract_media_v1(payload)

        self.assertEqual(media.crosspost, ["FB", "IG", "THREADS"])
        self.assertEqual(
            media.crosspost_metadata,
            {
                "fb_crosspost_fbid": "fb-media-id",
                "threads_crosspost_id": "threads-media-id",
            },
        )
        self.assertEqual(media.has_shared_to_fb, 3)

    async def test_feed_upload_crossposting_destination_type_annotations_are_literal(self):
        for method_name in ("photo_upload", "video_upload", "album_upload"):
            self.assert_fb_destination_type_literal(method_name, "fb_destination_type")

    async def test_photo_upload_adds_feed_crossposting_params_before_upload(self):
        client = self.build_client()
        original = {"disable_comments": 1}
        crosspost_data = {
            "disable_comments": 1,
            "share_to_facebook": "1",
            "share_to_threads": "1",
        }
        client._media_crossposting_extra_data = AsyncMock(return_value=crosspost_data)
        client._current_media_ids = AsyncMock(return_value=set())
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.photo_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_recent = AsyncMock(return_value="photo")

        with patch("asyncio.sleep", new=AsyncMock()):
            media = await client.photo_upload(
                Path("example.jpg"),
                "caption",
                extra_data=original,
                share_to_facebook=True,
                share_to_threads=True,
                fb_destination_id="fb-destination",
                fb_destination_type="PAGE",
                threads_destination_id="threads-destination",
            )

        self.assertEqual(media, "photo")
        self.assertEqual(original, {"disable_comments": 1})
        client._media_crossposting_extra_data.assert_awaited_once_with(
            {"disable_comments": 1},
            share_to_facebook=True,
            share_to_threads=True,
            fb_destination_id="fb-destination",
            fb_destination_type="PAGE",
            fb_validation_bypass=None,
            threads_destination_id="threads-destination",
            threads_validation_bypass=None,
        )
        client.photo_rupload.assert_awaited_once()
        self.assertEqual(client.photo_configure.call_args.kwargs["extra_data"], crosspost_data)

    async def test_video_upload_adds_feed_crossposting_params_before_upload(self):
        client = self.build_client()
        crosspost_data = {
            "share_to_facebook": "1",
            "share_to_threads": "1",
        }
        client._media_crossposting_extra_data = AsyncMock(return_value=crosspost_data)
        client.video_rupload = AsyncMock(return_value=("1", 720, 1280, 5, Path("/tmp/thumb.jpg")))
        client.video_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: "video"

        with patch("asyncio.sleep", new=AsyncMock()):
            media = await client.video_upload(
                Path("example.mp4"),
                "caption",
                share_to_facebook=True,
                share_to_threads=True,
                fb_destination_id="fb-destination",
                fb_destination_type="USER",
                threads_destination_id="threads-destination",
            )

        self.assertEqual(media, "video")
        client._media_crossposting_extra_data.assert_awaited_once_with(
            {},
            share_to_facebook=True,
            share_to_threads=True,
            fb_destination_id="fb-destination",
            fb_destination_type="USER",
            fb_validation_bypass=None,
            threads_destination_id="threads-destination",
            threads_validation_bypass=None,
        )
        client.video_rupload.assert_awaited_once()
        self.assertEqual(client.video_configure.call_args.kwargs["extra_data"], crosspost_data)

    async def test_album_upload_adds_feed_crossposting_params_before_upload(self):
        client = self.build_client()
        crosspost_data = {
            "share_to_facebook": "1",
            "share_to_threads": "1",
        }
        client._media_crossposting_extra_data = AsyncMock(return_value=crosspost_data)
        client.photo_rupload = AsyncMock(return_value=("1", 720, 720))
        client.album_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: "album"

        with patch("asyncio.sleep", new=AsyncMock()):
            media = await client.album_upload(
                [Path("one.jpg")],
                "caption",
                configure_timeout=0,
                share_to_facebook=True,
                share_to_threads=True,
                fb_destination_id="fb-destination",
                fb_destination_type="PAGE",
                threads_destination_id="threads-destination",
            )

        self.assertEqual(media, "album")
        client._media_crossposting_extra_data.assert_awaited_once_with(
            {},
            share_to_facebook=True,
            share_to_threads=True,
            fb_destination_id="fb-destination",
            fb_destination_type="PAGE",
            fb_validation_bypass=None,
            threads_destination_id="threads-destination",
            threads_validation_bypass=None,
        )
        client.photo_rupload.assert_awaited_once()
        self.assertEqual(client.album_configure.call_args.kwargs["extra_data"], crosspost_data)

    async def test_feed_crossposting_preflight_fails_before_uploading_bytes(self):
        cases = (
            (
                "photo",
                "photo_rupload",
                lambda client: client.photo_upload(
                    Path("example.jpg"),
                    "caption",
                    share_to_threads=True,
                ),
            ),
            (
                "video",
                "video_rupload",
                lambda client: client.video_upload(
                    Path("example.mp4"),
                    "caption",
                    share_to_threads=True,
                ),
            ),
            (
                "album",
                "photo_rupload",
                lambda client: client.album_upload(
                    [Path("one.jpg")],
                    "caption",
                    share_to_threads=True,
                ),
            ),
        )

        for label, upload_method, invoke in cases:
            with self.subTest(label=label):
                client = self.build_client()
                client._media_crossposting_extra_data = AsyncMock(side_effect=ClientError("no linked Threads profile"))
                upload = AsyncMock()
                setattr(client, upload_method, upload)

                with self.assertRaises(ClientError):
                    await invoke(client)

                upload.assert_not_awaited()

    async def test_feed_music_uploads_forward_crossposting_options(self):
        client = self.build_client()
        client._feed_music_params = AsyncMock(return_value={"audio_asset_id": "track-id"})
        track = {"id": "track-id"}
        options = {
            "share_to_facebook": True,
            "share_to_threads": True,
            "fb_destination_id": "fb-destination",
            "fb_destination_type": "USER",
            "threads_destination_id": "threads-destination",
        }

        client.photo_upload = AsyncMock(return_value="photo")
        result = await client.photo_upload_with_music(
            Path("one.jpg"),
            "caption",
            track,
            **options,
        )
        self.assertEqual(result, "photo")
        for key, value in options.items():
            self.assertEqual(client.photo_upload.call_args.kwargs[key], value)

        client.album_upload = AsyncMock(return_value="album")
        result = await client.album_upload_with_music(
            [Path("one.jpg"), Path("two.jpg")],
            "caption",
            track,
            **options,
        )
        self.assertEqual(result, "album")
        for key, value in options.items():
            self.assertEqual(client.album_upload.call_args.kwargs[key], value)

    async def test_clip_upload_share_to_threads_adds_crosspost_params(self):
        client = self.build_client()
        client.authorization_data = {
            "ds_user_id": "1",
            "sessionid": "1:session",
            "should_use_header_over_cookies": True,
        }
        ok_response = Mock(status_code=200)
        client.private.get = AsyncMock(return_value=ok_response)
        client.private.post = AsyncMock(side_effect=[ok_response, ok_response])
        client.clip_configure = AsyncMock(return_value={"status": "ok"})
        client._extract_configured_media_or_raise = lambda configured, *args, **kwargs: "clip"
        threads_extra = {
            "share_to_threads": "1",
            "share_to_threads_destination_id": "threads-destination",
        }
        client.media_share_to_threads_extra_data = AsyncMock(return_value=threads_extra)

        with patch(
            "aiograpi.mixins.clip.analyze_video",
            return_value=(Path("/tmp/thumb.jpg"), 720, 1280, 6.023),
        ):
            with patch("builtins.open", mock_open(read_data=b"video-bytes")):
                with patch("asyncio.sleep", new=AsyncMock()):
                    media = await client.clip_upload(
                        Path("example.mp4"),
                        "caption",
                        share_to_threads=True,
                        threads_destination_id="threads-destination",
                    )

        self.assertEqual(media, "clip")
        client.media_share_to_threads_extra_data.assert_awaited_once_with(
            destination_id="threads-destination",
            validation_bypass=None,
        )
        self.assertEqual(client.clip_configure.call_args.kwargs["extra_data"], threads_extra)
