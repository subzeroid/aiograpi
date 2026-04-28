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
    pass


class WrongCursorError(ClientError):
    message = "You specified a non-existent cursor"


class ClientStatusFail(ClientError):
    pass


class ClientErrorWithTitle(ClientError):
    pass


class ResetPasswordError(ClientError):
    pass


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
    pass


class PrivateError(ClientError):
    """For Private API and last_json logic"""


class NotFoundError(PrivateError):
    reason = "Not found"


class FeedbackRequired(PrivateError):
    pass


class ChallengeError(PrivateError):
    pass


class ChallengeRedirection(ChallengeError):
    pass


class ChallengeRequired(ChallengeError):
    pass


class ChallengeSelfieCaptcha(ChallengeError):
    pass


class ChallengeUnknownStep(ChallengeError):
    pass


class SelectContactPointRecoveryForm(ChallengeError):
    pass


class RecaptchaChallengeForm(ChallengeError):
    pass


class SubmitPhoneNumberForm(ChallengeError):
    pass


class LegacyForceSetNewPasswordForm(ChallengeError):
    pass


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
    pass


class RateLimitError(PrivateError):
    pass


class ProxyAddressIsBlocked(PrivateError):
    """Instagram has blocked your IP address, use a quality proxy provider (not free, not shared)"""


class BadPassword(PrivateError):
    pass


class BadCredentials(PrivateError):
    pass


class PleaseWaitFewMinutes(PrivateError):
    pass


class UnknownError(PrivateError):
    pass


class TrackNotFound(NotFoundError):
    pass


class MediaError(PrivateError):
    pass


class MediaNotFound(NotFoundError, MediaError):
    pass


class StoryNotFound(NotFoundError, MediaError):
    pass


class UserError(PrivateError):
    pass


class UserNotFound(NotFoundError, UserError):
    pass


class CollectionError(PrivateError):
    pass


class CollectionNotFound(NotFoundError, CollectionError):
    pass


class DirectError(PrivateError):
    pass


class DirectThreadNotFound(NotFoundError, DirectError):
    pass


class DirectMessageNotFound(NotFoundError, DirectError):
    pass


class VideoTooLongException(PrivateError):
    pass


class VideoNotDownload(PrivateError):
    pass


class VideoNotUpload(PrivateError):
    pass


class VideoConfigureError(VideoNotUpload):
    pass


class VideoConfigureStoryError(VideoConfigureError):
    pass


class PhotoNotUpload(PrivateError):
    pass


class PhotoConfigureError(PhotoNotUpload):
    pass


class PhotoConfigureStoryError(PhotoConfigureError):
    pass


class IGTVNotUpload(PrivateError):
    pass


class IGTVConfigureError(IGTVNotUpload):
    pass


class ClipNotUpload(PrivateError):
    pass


class ClipConfigureError(ClipNotUpload):
    pass


class AlbumNotDownload(PrivateError):
    pass


class AlbumUnknownFormat(PrivateError):
    pass


class AlbumConfigureError(PrivateError):
    pass


class HashtagError(PrivateError):
    pass


class HashtagNotFound(NotFoundError, HashtagError):
    pass


class HashtagPageWarning(ClientForbiddenError, HashtagError):
    pass


class LocationError(PrivateError):
    pass


class LocationNotFound(NotFoundError, LocationError):
    pass


class TwoFactorRequired(PrivateError):
    pass


class HighlightNotFound(NotFoundError, PrivateError):
    pass


class InvalidNonce(PrivateError):
    pass


class NoteNotFound(NotFoundError):
    reason = "Not found"


class ConsentRequired(PrivateError):
    pass


class GeoBlockRequired(PrivateError):
    pass


class CheckpointRequired(PrivateError):
    pass


class PrivateAccount(PrivateError):
    """This Account is Private"""


class InvalidTargetUser(PrivateError):
    """Invalid target user"""


class InvalidMediaId(PrivateError):
    """Invalid media_id"""


class MediaUnavailable(PrivateError):
    """Media is unavailable"""


class CommentUnavailable(PrivateError):
    """Comment is unavailable"""


class CommentNotFound(PrivateError):
    message = "Comment not found"


class CommentsDisabled(PrivateError):
    message = "Comments disabled by author"


class ShareDecodeError(PrivateError):
    pass


class AccountSuspended(ClientError):
    pass


class TermsUnblock(ClientError):
    pass


class TermsAccept(ClientError):
    pass


class AboutUsError(ClientError):
    pass


class RelatedProfileRequired(ClientError):
    """Raised by user_related_profiles_gql when IG returns no related
    profiles. Upstream hiker-next uses this as a retry signal; in
    aiograpi the method returns an empty list instead, so this is
    exposed for callers that want to opt into the same retry
    semantics by setting ``client.num_retry`` themselves."""

    pass


class IsRegulatedC18Error(ClientBadRequestError):
    """Instagram has limited access to users by age (18+)"""


class ProxyError(ClientError):
    pass


class ConnectProxyError(ProxyError):
    """ProxyError is raised due to a HTTP 401 response"""


class AuthRequiredProxyError(ProxyError):
    """ProxyError is raised due to a HTTP 407 response"""


class UnsupportedError(ClientError):
    def __init__(self, value, items):
        message = f'Unsupported value="{value}" {items}'
        super().__init__(message)


class UnsupportedSettingValue(UnsupportedError):
    pass


class PreLoginRequired(ClientError):
    message = "Login required"


class ValidationError(AssertionError):
    pass


class EmailInvalidError(ClientError):
    pass


class EmailNotAvailableError(ClientError):
    pass


class EmailVerificationSendError(ClientError):
    pass


class AgeEligibilityError(ClientError):
    pass


class CaptchaChallengeRequired(ClientError):
    """Captcha challenge required, and no solver is configured or available."""

    def __init__(
        self,
        message="Captcha challenge required, but no solver configured or available.",
        challenge_details=None,
        **kwargs,
    ):
        self.challenge_details = challenge_details if challenge_details else {}
        super().__init__(message, **kwargs)
