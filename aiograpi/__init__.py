import logging
from copy import deepcopy
from typing import Optional
from urllib.parse import urlparse

from aiograpi.mixins.account import AccountMixin
from aiograpi.mixins.album import DownloadAlbumMixin, UploadAlbumMixin
from aiograpi.mixins.auth import LoginMixin
from aiograpi.mixins.bloks import BloksMixin
from aiograpi.mixins.challenge import ChallengeResolveMixin
from aiograpi.mixins.clip import DownloadClipMixin, UploadClipMixin
from aiograpi.mixins.collection import CollectionMixin
from aiograpi.mixins.comment import CommentMixin
from aiograpi.mixins.direct import DirectMixin
from aiograpi.mixins.explore import ExploreMixin
from aiograpi.mixins.fbsearch import FbSearchMixin
from aiograpi.mixins.fundraiser import FundraiserMixin
from aiograpi.mixins.graphql import GraphQLRequestMixin
from aiograpi.mixins.hashtag import HashtagMixin
from aiograpi.mixins.highlight import HighlightMixin
from aiograpi.mixins.igtv import DownloadIGTVMixin, UploadIGTVMixin
from aiograpi.mixins.insights import InsightsMixin
from aiograpi.mixins.location import LocationMixin
from aiograpi.mixins.media import MediaMixin
from aiograpi.mixins.multiple_accounts import MultipleAccountsMixin
from aiograpi.mixins.note import NoteMixin
from aiograpi.mixins.notification import NotificationMixin
from aiograpi.mixins.password import PasswordMixin
from aiograpi.mixins.photo import DownloadPhotoMixin, UploadPhotoMixin
from aiograpi.mixins.private import PrivateRequestMixin
from aiograpi.mixins.public import (
    ProfilePublicMixin,
    PublicRequestMixin,
    TopSearchesPublicMixin,
)
from aiograpi.mixins.share import ShareMixin
from aiograpi.mixins.signup import SignUpMixin
from aiograpi.mixins.story import StoryMixin
from aiograpi.mixins.timeline import ReelsMixin
from aiograpi.mixins.totp import TOTPMixin
from aiograpi.mixins.track import TrackMixin
from aiograpi.mixins.user import UserMixin
from aiograpi.mixins.video import DownloadVideoMixin, UploadVideoMixin

# Used as fallback logger if another is not provided.
DEFAULT_LOGGER = logging.getLogger("aiograpi")


class Client(
    MultipleAccountsMixin,
    NoteMixin,
    GraphQLRequestMixin,
    PublicRequestMixin,
    ChallengeResolveMixin,
    PrivateRequestMixin,
    TopSearchesPublicMixin,
    ProfilePublicMixin,
    LoginMixin,
    ShareMixin,
    TrackMixin,
    FbSearchMixin,
    HighlightMixin,
    DownloadPhotoMixin,
    UploadPhotoMixin,
    DownloadVideoMixin,
    UploadVideoMixin,
    DownloadAlbumMixin,
    NotificationMixin,
    UploadAlbumMixin,
    DownloadIGTVMixin,
    UploadIGTVMixin,
    MediaMixin,
    UserMixin,
    InsightsMixin,
    CollectionMixin,
    AccountMixin,
    DirectMixin,
    LocationMixin,
    HashtagMixin,
    CommentMixin,
    StoryMixin,
    PasswordMixin,
    SignUpMixin,
    DownloadClipMixin,
    UploadClipMixin,
    ReelsMixin,
    ExploreMixin,
    BloksMixin,
    TOTPMixin,
    FundraiserMixin,
):
    proxy = None

    def __init__(
        self,
        settings: Optional[dict] = None,
        proxy: Optional[str] = None,
        delay_range: Optional[list] = None,
        logger=DEFAULT_LOGGER,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.settings = deepcopy(settings or {})
        self.logger = logger
        self.delay_range = delay_range
        self.set_proxy(proxy)
        self.init()

    def set_proxy(self, dsn: Optional[str]):
        if not dsn:
            self.public.proxy = self.private.proxy = self.graphql.proxy = None
            return False
        assert isinstance(
            dsn, str
        ), f'Proxy must been string (URL), but now "{dsn}" ({type(dsn)})'
        self.proxy = dsn
        proxy_href = "{scheme}{href}".format(
            scheme="http://" if not urlparse(self.proxy).scheme else "",
            href=self.proxy,
        )
        self.public.proxy = self.private.proxy = self.graphql.proxy = proxy_href
        return True
