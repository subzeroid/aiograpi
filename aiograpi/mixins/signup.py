import asyncio
import base64
from datetime import datetime
from uuid import uuid4

from aiograpi.exceptions import InvalidNonce
from aiograpi.extractors import extract_user_short
from aiograpi.mixins.challenge import ChallengeChoice
from aiograpi.types import UserShort
from aiograpi.utils import generate_jazoest


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
        check = await self.check_username(username)
        if not check.get("available"):
            raise Exception(f"Username is't available ({check})")
        kwargs = {
            "username": username,
            "password": password,
            "full_name": full_name,
            "year": year,
            "month": month,
            "day": day,
        }
        if email:
            kwargs["email"] = email
            check = await self.check_email(email)
            if not check.get("valid"):
                raise Exception(f"Email not valid ({check})")
            if not check.get("available"):
                raise Exception(f"Email not available ({check})")
            config = await self.get_signup_config()
            sent = await self.send_verify_email(email)
            if not sent.get("email_sent"):
                raise Exception("Email not sent ({sent})")
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
            kwargs["email_code"] = self.check_confirmation_code(email, code).get(
                "signup_code"
            )
        if phone_number:
            kwargs["phone_number"] = phone_number
            config = await self.get_signup_config()
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
        if "tos_version" in config:
            kwargs["tos_version"] = config["tos_version"]
        while retries < 3:
            data = await self.accounts_create(**kwargs)
            if data.get("error_type") == "invalid_nonce":
                raise InvalidNonce(data["errors"]["nonce"][0])
            if data.get("message") != "challenge_required":
                break  # SUCCESS EXIT
            if self.challenge_flow(data["challenge"]):
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
        """Check available (free, not registred) email"""
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
        return await self.private.post(
            "consent/check_age_eligibility/",
            data={"_csrftoken": self.token, "day": day, "year": year, "month": month},
        ).json()

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
        timestamp = datetime.now().strftime("%s")
        self.username = username
        self.password = password
        data = {
            "jazoest": generate_jazoest(self.phone_id),
            "suggestedUsername": "",
            "do_not_auto_login_if_credentials_match": "true",  # C#
            "phone_id": self.phone_id,
            "enc_password": await self.password_encrypt(password),
            "username": username,
            "first_name": str(full_name),
            "adid": self.adid,
            "guid": self.uuid,
            "year": str(year),
            "month": str(month),
            "day": str(day),
            "device_id": self.android_device_id,
            "_uuid": self.uuid,
            "waterfall_id": self.waterfall_id,
            "one_tap_opt_in": "true",  # C#
            "_csrftoken": self.token,  # C#
            # "sn_result": "GOOGLE_PLAY_UNAVAILABLE:SERVICE_INVALID",  #C#
            **kwargs,
        }
        if self.user_id:
            data["logged_in_user_authorization_token"] = self.authorization
            data["logged_in_user_id"] = str(self.user_id)
        if email and not phone_number:  # EMAIL
            endpoint = "accounts/create/"
            # $"{emailOrPhoneNumber}|{DateTimeHelper.ToUnixTime(DateTime.UtcNow)}|{Encoding.UTF8.GetString(b)}";
            nonce = f'{email}|{timestamp}|\xb9F"\x8c\xa2I\xaaz|\xf6xz\x86\x92\x91Y\xa5\xaa#f*o%\x7f'
            sn_nonce = base64.encodebytes(nonce.encode()).decode().strip()
            data = dict(
                data,
                **{
                    "email": email,
                    "is_secondary_account_creation": "true",  # C#
                    "force_sign_up_code": email_code,
                    "sn_nonce": sn_nonce,
                    "qs_stamp": "",  # C#
                },
            )
        else:  # PHONE
            endpoint = "accounts/create_validated/"
            # $"{emailOrPhoneNumber}|{DateTimeHelper.ToUnixTime(DateTime.UtcNow)}|{Encoding.UTF8.GetString(b)}";
            nonce = f'{phone_number}|{timestamp}|\xb9F"\x8c\xa2I\xaaz|\xf6xz\x86\x92\x91Y\xa5\xaa#f*o%\x7f'
            sn_nonce = base64.encodebytes(nonce.encode()).decode().strip()
            data = dict(
                data,
                **{
                    "phone_number": phone_number,
                    "is_secondary_account_creation": "true"
                    if data.get("logged_in_user_id")
                    else "false",
                    "verification_code": phone_code,
                    "force_sign_up_code": "",
                    "has_sms_consent": "true",
                    # "sn_nonce": sn_nonce
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

    async def challenge_captcha(self, data):
        g_recaptcha_response = await self.captcha_resolve()
        resp = await self.private.post(
            f"https://i.instagram.com{data['api_path']}",
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
        resp = await self.private_request(
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
        return resp

    async def send_signup_sms_code(self, phone_number: str):
        resp = await self.private_request(
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
        return resp
