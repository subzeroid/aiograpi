import asyncio
import base64
import random
import secrets
import time
from uuid import uuid4

from aiograpi.exceptions import (
    AgeEligibilityError,
    CaptchaChallengeRequired,
    ClientError,
    EmailInvalidError,
    EmailNotAvailableError,
    EmailVerificationSendError,
    InvalidNonce,
)
from aiograpi.extractors import extract_user_short
from aiograpi.mixins.challenge import ChallengeChoice
from aiograpi.types import UserShort

CHOICE_EMAIL = 1


class SignUpMixin:
    waterfall_id = str(uuid4())
    adid = str(uuid4())
    wait_seconds = 5

    async def signup(
        self,
        username: str,
        password: str,
        email: str = "",
        phone_number: str = "",
        full_name: str = "",
        year: int = None,
        month: int = None,
        day: int = None,
    ) -> UserShort:
        if not (email or phone_number):
            raise Exception("Use email or phone_number")
        await self.get_signup_config()
        kwargs = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "year": year,
            "month": month,
            "day": day,
        }
        if email:
            check = await self.check_email(email)
            if not check.get("valid"):
                raise EmailInvalidError(
                    f"Email not valid: {check.get('error_title', check)}"
                )
            if not check.get("available"):
                raise EmailNotAvailableError(
                    f"Email not available: {check.get('feedback_message', check)}"
                )
            sent = await self.send_verify_email(email)
            if not sent.get("email_sent"):
                raise EmailVerificationSendError(
                    f"Failed to send verification email: {sent}"
                )

            # Date of Birth (DOB) Age Eligibility Check
            if year and month and day:
                age_check_result = await self.check_age_eligibility(year, month, day)
                if not age_check_result.get("eligible"):
                    raise AgeEligibilityError(
                        f"Account not eligible based on age criteria: {age_check_result}"
                    )

            # send code confirmation
            code = ""
            for attempt in range(1, 11):
                code = await self.challenge_code_handler(
                    username, ChallengeChoice.EMAIL
                )
                if code:
                    break
                await asyncio.sleep(self.wait_seconds * attempt)
            print(
                f'Enter code "{code}" for {username} '
                f"({attempt} attempts, by {self.wait_seconds} seconds)"
            )
            confirmation_result = await self.check_confirmation_code(email, code)
            kwargs["email"] = email
            kwargs["email_code"] = confirmation_result.get("signup_code")

        if phone_number:
            kwargs["phone_number"] = phone_number
            check = await self.check_phone_number(phone_number)
            if check.get("status") != "ok":
                raise Exception(f"Phone number not valid ({check})")
            sms = await self.send_signup_sms_code(phone_number)
            if check.get("status") != "ok":
                raise Exception(f"Error when verify phone number ({sms})")
            if "verification_code" in sms:
                # when you have multiple accounts
                code = sms["verification_code"]
            else:
                for attempt in range(1, 11):
                    code = await self.challenge_code_handler(
                        username, ChallengeChoice.SMS
                    )
                    if code:
                        break
                    await asyncio.sleep(self.wait_seconds * attempt)
            print(
                f'Enter code "{code}" for {username} '
                f"({attempt} attempts, by {self.wait_seconds} seconds)"
            )
            kwargs["phone_code"] = code

        retries = 0
        while retries < 3:
            data = await self.accounts_create(**kwargs)
            if data.get("error_type") == "invalid_nonce":
                raise InvalidNonce(data["errors"]["nonce"][0])
            if data.get("message") != "challenge_required":
                break  # SUCCESS EXIT
            if await self.challenge_flow(data["challenge"]):
                kwargs.update({"suggestedUsername": "", "sn_result": "MLA"})
            retries += 1
        self.authorization_data = self.parse_authorization(
            self.last_response.headers.get("ig-set-authorization")
        )
        try:
            return extract_user_short(data["created_user"])
        except Exception as e:
            print(f"ERROR: {e}", data)

    async def check_username(self, username):
        return await self.private_request(
            "users/check_username/", data={"username": username, "_uuid": self.uuid}
        )

    async def get_signup_config(self) -> dict:
        return await self.private_request(
            "consent/get_signup_config/",
            params={"guid": self.uuid, "main_account_selected": False},
        )

    async def check_email(self, email) -> dict:
        """Check available (free, not registered) email"""
        return await self.private_request(
            "users/check_email/",
            {
                "android_device_id": self.android_device_id,
                "login_nonce_map": "{}",
                "login_nonces": "[]",
                "email": email,
                "qe_id": str(uuid4()),
                "waterfall_id": self.waterfall_id,
            },
        )

    async def send_verify_email(self, email) -> dict:
        """Send request to receive code to email"""
        return await self.private_request(
            "accounts/send_verify_email/",
            {
                "phone_id": self.phone_id,
                "device_id": self.android_device_id,
                "email": email,
                "waterfall_id": self.waterfall_id,
                "auto_confirm_only": "false",
            },
        )

    async def check_confirmation_code(self, email, code) -> dict:
        """Enter code from email"""
        return await self.private_request(
            "accounts/check_confirmation_code/",
            {
                "code": code,
                "device_id": self.android_device_id,
                "email": email,
                "waterfall_id": self.waterfall_id,
            },
        )

    async def check_age_eligibility(self, year, month, day):
        return await self.private_request(
            "consent/check_age_eligibility/",
            data={"_csrftoken": self.token, "day": day, "year": year, "month": month},
            with_signature=False,
        )

    async def accounts_create(
        self,
        username: str,
        password: str,
        email: str = "",
        email_code: str = "",  # signup_code
        phone_number: str = "",
        phone_code: str = "",  # verification_code
        full_name: str = "",
        year: int = None,
        month: int = None,
        day: int = None,
        **kwargs,
    ) -> dict:
        timestamp = str(int(time.time()))
        self.username = username
        self.password = password
        data = {
            "is_secondary_account_creation": "true",
            "jazoest": str(random.randint(22300, 22399)),
            "tos_version": "row",
            "suggestedUsername": "",
            "sn_result": "",
            "do_not_auto_login_if_credentials_match": "false",
            "phone_id": self.phone_id,
            "enc_password": await self.password_encrypt(password),
            "username": username,
            "first_name": str(full_name),
            "adid": self.adid,
            "guid": self.uuid,
            "day": day,
            "month": month,
            "year": year,
            "device_id": self.android_device_id,
            "_uuid": self.uuid,
            "waterfall_id": self.waterfall_id,
            "one_tap_opt_in": "true",
            **kwargs,
        }
        if self.user_id:
            data["logged_in_user_authorization_token"] = self.authorization
            data["logged_in_user_id"] = str(self.user_id)
        if email and not phone_number:  # EMAIL
            endpoint = "accounts/create/"
            nonce_bytes = secrets.token_bytes(24)
            nonce = f"{email}|{timestamp}|".encode() + nonce_bytes
            sn_nonce = base64.encodebytes(nonce).decode().strip()
            data = dict(
                data,
                **{
                    "email": email,
                    "force_sign_up_code": email_code,
                    "sn_nonce": sn_nonce,
                    "qs_stamp": "",
                },
            )
        else:  # PHONE
            endpoint = "accounts/create_validated/"
            nonce_bytes = secrets.token_bytes(24)
            nonce = f"{phone_number}|{timestamp}|".encode() + nonce_bytes
            sn_nonce = base64.encodebytes(nonce).decode().strip()
            data = dict(
                data,
                **{
                    "phone_number": phone_number,
                    "is_secondary_account_creation": (
                        "true" if data.get("logged_in_user_id") else "false"
                    ),
                    "verification_code": phone_code,
                    "force_sign_up_code": "",
                    "has_sms_consent": "true",
                },
            )
        return await self.private_request(endpoint, data)

    async def challenge_flow(self, data):
        data = await self.challenge_api(data)
        while True:
            if data.get("message") == "challenge_required":
                data = await self.challenge_captcha(data["challenge"])
                continue
            elif data.get("challengeType") == "SubmitPhoneNumberForm":
                data = await self.challenge_submit_phone_number(data)
                continue
            elif data.get("challengeType") == "VerifySMSCodeFormForSMSCaptcha":
                data = await self.challenge_verify_sms_captcha(data)
                continue

    async def challenge_api(self, data):
        resp = await self.private.get(
            f"https://i.instagram.com/api/v1{data['api_path']}",
            params={
                "guid": self.uuid,
                "device_id": self.android_device_id,
                "challenge_context": data["challenge_context"],
            },
        )
        return resp.json()

    async def challenge_captcha(self, challenge_json_data):
        api_path = challenge_json_data.get("api_path")
        site_key = challenge_json_data.get("fields", {}).get("sitekey")
        challenge_type = challenge_json_data.get("challengeType")  # For logging/context

        if not site_key or not api_path:
            self.logger.error(
                f"Malformed captcha challenge data from Instagram: site_key={site_key}, api_path={api_path}"
            )
            raise ClientError(
                "Malformed captcha challenge data from Instagram (missing site_key or api_path)."
            )

        challenge_post_url = f"https://i.instagram.com{api_path}"
        captcha_details_for_solver = {
            "site_key": site_key,
            "challenge_type": challenge_type,
            "raw_challenge_json": challenge_json_data,
            "page_url": "https://www.instagram.com/accounts/emailsignup/",
        }

        try:
            g_recaptcha_response = await self.captcha_resolve(
                **captcha_details_for_solver
            )
        except CaptchaChallengeRequired:
            self.logger.warning(
                "Captcha solution was required by Instagram but not provided/resolved by any configured handler."
            )
            raise  # Re-raise for the user of aiograpi to handle or be informed.
        except Exception as e:
            self.logger.error(
                f"An unexpected error occurred during the captcha resolution process: {e}",
                exc_info=True,
            )
            raise ClientError(f"Captcha resolution process failed: {e}")

        resp = await self.private.post(
            challenge_post_url,
            data={"g-recaptcha-response": g_recaptcha_response},
        )
        return resp.json()

    async def challenge_submit_phone_number(self, data, phone_number):
        api_path = data.get("navigation", {}).get("forward")
        resp = await self.private.post(
            f"https://i.instagram.com{api_path}",
            data={
                "phone_number": phone_number,
                "challenge_context": data["challenge_context"],
            },
        )
        return resp.json()

    async def challenge_verify_sms_captcha(self, data, security_code):
        api_path = data.get("navigation", {}).get("forward")
        resp = await self.private.post(
            f"https://i.instagram.com{api_path}",
            data={
                "security_code": security_code,
                "challenge_context": data["challenge_context"],
            },
        )
        return resp.json()

    async def check_phone_number(self, phone_number: str):
        return await self.private_request(
            "accounts/check_phone_number/",
            data={
                "phone_id": self.phone_id,
                "login_nonce_map": "{}",
                "phone_number": phone_number.replace(" ", "+"),
                "guid": self.uuid,
                "device_id": self.android_device_id,
                "prefill_shown": "False",
            },
        )

    async def send_signup_sms_code(self, phone_number: str):
        return await self.private_request(
            "accounts/send_signup_sms_code/",
            data={
                "phone_id": self.phone_id,
                "phone_number": phone_number.replace(" ", "+"),
                "guid": self.uuid,
                "device_id": self.android_device_id,
                "android_build_type": "release",
                "waterfall_id": self.waterfall_id,
            },
        )
