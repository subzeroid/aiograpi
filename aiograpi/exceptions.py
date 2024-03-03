class ClientError(Exception):
    response = None
    code = None
    message = ""

    def __init__(self, *args, **kwargs):
        args = list(args)
        if len(args) > 0:
            self.message = str(args.pop(0))
        for key in list(kwargs.keys()):
            setattr(self, key, kwargs.pop(key))
        if not self.message:
            self.message = "{title} ({body})".format(
                title=getattr(self, "reason", "Unknown"),
                body=getattr(self, "error_type", vars(self)),
            )
        super().__init__(self.message, *args, **kwargs)
        if self.response:
            self.code = self.response.status_code


class ClientUnknownError(ClientError):
    ...


class WrongCursorError(ClientError):
    message = "You specified a non-existent cursor"


class ClientStatusFail(ClientError):
    ...


class ClientErrorWithTitle(ClientError):
    ...


class ResetPasswordError(ClientError):
    ...


class GenericRequestError(ClientError):
    """Sorry, there was a problem with your request"""


class ClientGraphqlError(ClientError):
    """Raised due to graphql issues"""


class ClientJSONDecodeError(ClientError):
    """Raised due to json decoding issues"""


class ClientConnectionError(ClientError):
    """Raised due to network connectivity-related issues"""


class ClientBadRequestError(ClientError):
    """Raised due to a HTTP 400 response"""


class ClientUnauthorizedError(ClientError):
    """Raised due to a HTTP 401 response"""


class ClientForbiddenError(ClientError):
    """Raised due to a HTTP 403 response"""


class ClientNotFoundError(ClientError):
    """Raised due to a HTTP 404 response"""


class ClientThrottledError(ClientError):
    """Raised due to a HTTP 429 response"""


class ClientRequestTimeout(ClientError):
    """Raised due to a HTTP 408 response"""


class ClientIncompleteReadError(ClientError):
    """Raised due to incomplete read HTTP response"""


class ClientLoginRequired(ClientError):
    """Instagram redirect to https://www.instagram.com/accounts/login/"""


class ReloginAttemptExceeded(ClientError):
    ...


class IsRegulatedC18Error(ClientBadRequestError):
    """Instagram has limited access to users by age (18+)"""


class PrivateError(ClientError):
    """For Private API and last_json logic"""


class NotFoundError(PrivateError):
    reason = "Not found"


class FeedbackRequired(PrivateError):
    ...


class ChallengeError(PrivateError):
    ...


class ChallengeRedirection(ChallengeError):
    ...


class ChallengeRequired(ChallengeError):
    ...


class ChallengeSelfieCaptcha(ChallengeError):
    ...


class ChallengeUnknownStep(ChallengeError):
    ...


class SelectContactPointRecoveryForm(ChallengeError):
    ...


class RecaptchaChallengeForm(ChallengeError):
    ...


class SubmitPhoneNumberForm(ChallengeError):
    ...


class LegacyForceSetNewPasswordForm(ChallengeError):
    ...


class LoginRequired(PrivateError):
    """Instagram request relogin
    Example:
    {'message': 'login_required',
    'response': <Response [403]>,
    'error_title': "You've Been Logged Out",
    'error_body': 'Please log back in.',
    'logout_reason': 8,
    'status': 'fail'}
    """


class SentryBlock(PrivateError):
    ...


class RateLimitError(PrivateError):
    ...


class ProxyAddressIsBlocked(PrivateError):
    """Instagram has blocked your IP address,
    use a quality proxy provider (not free, not shared)
    """


class BadPassword(PrivateError):
    ...


class BadCredentials(PrivateError):
    ...


class PleaseWaitFewMinutes(PrivateError):
    ...


class UnknownError(PrivateError):
    ...


class TrackNotFound(NotFoundError):
    ...


class MediaError(PrivateError):
    ...


class MediaNotFound(NotFoundError, MediaError):
    ...


class StoryNotFound(NotFoundError, MediaError):
    ...


class UserError(PrivateError):
    ...


class UserNotFound(NotFoundError, UserError):
    ...


class CollectionError(PrivateError):
    ...


class CollectionNotFound(NotFoundError, CollectionError):
    ...


class DirectError(PrivateError):
    ...


class DirectThreadNotFound(NotFoundError, DirectError):
    ...


class DirectMessageNotFound(NotFoundError, DirectError):
    ...


class VideoTooLongException(PrivateError):
    ...


class VideoNotDownload(PrivateError):
    ...


class VideoNotUpload(PrivateError):
    ...


class VideoConfigureError(VideoNotUpload):
    ...


class VideoConfigureStoryError(VideoConfigureError):
    ...


class PhotoNotUpload(PrivateError):
    ...


class PhotoConfigureError(PhotoNotUpload):
    ...


class PhotoConfigureStoryError(PhotoConfigureError):
    ...


class IGTVNotUpload(PrivateError):
    ...


class IGTVConfigureError(IGTVNotUpload):
    ...


class ClipNotUpload(PrivateError):
    ...


class ClipConfigureError(ClipNotUpload):
    ...


class AlbumNotDownload(PrivateError):
    ...


class AlbumUnknownFormat(PrivateError):
    ...


class AlbumConfigureError(PrivateError):
    ...


class HashtagError(PrivateError):
    ...


class HashtagNotFound(NotFoundError, HashtagError):
    ...


class HashtagPageWarning(ClientForbiddenError, HashtagError):
    ...


class LocationError(PrivateError):
    ...


class LocationNotFound(NotFoundError, LocationError):
    ...


class TwoFactorRequired(PrivateError):
    ...


class HighlightNotFound(NotFoundError, PrivateError):
    ...


class InvalidNonce(PrivateError):
    ...


class NoteNotFound(NotFoundError):
    reason = "Not found"


class ConsentRequired(PrivateError):
    ...


class GeoBlockRequired(PrivateError):
    ...


class CheckpointRequired(PrivateError):
    ...


class PrivateAccount(PrivateError):
    """This Account is Private"""


class InvalidTargetUser(PrivateError):
    """Invalid target user"""


class InvalidMediaId(PrivateError):
    """Invalid media_id"""


class MediaUnavailable(PrivateError):
    """Media is unavailable"""


class CommentNotFound(PrivateError):
    message = "Comment not found"


class CommentsDisabled(PrivateError):
    message = "Comments disabled by author"


class ShareDecodeError(PrivateError):
    ...


class AccountSuspended(ClientError):
    ...


class TermsUnblock(ClientError):
    ...


class TermsAccept(ClientError):
    ...


class AboutUsError(ClientError):
    ...


class ProxyError(ClientError):
    ...


class ConnectProxyError(ProxyError):
    """ProxyError is raised due to a HTTP 401 response"""


class AuthRequiredProxyError(ProxyError):
    """ProxyError is raised due to a HTTP 407 response"""


class UnsupportedError(ClientError):
    def __init__(self, value, items):
        message = f'Unsupported value="{value}" {items}'
        super().__init__(message)


class UnsupportedSettingValue(UnsupportedError):
    ...


class PreLoginRequired(ClientError):
    message = "Login required"
