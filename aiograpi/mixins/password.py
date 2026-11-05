import base64
import time

import httpx
from Cryptodome.Cipher import AES, PKCS1_v1_5
from Cryptodome.PublicKey import RSA
from Cryptodome.Random import get_random_bytes

from aiograpi.exceptions import ClientError
from aiograpi.mixins.base import ClientMixin


class PasswordMixin(ClientMixin):
    async def password_encrypt(self, password):
        publickeyid, publickey = await self.password_publickeys()
        session_key = get_random_bytes(32)

        iv = get_random_bytes(12)
        timestamp = str(int(time.time()))
        decoded_publickey = base64.b64decode(publickey.encode())
        recipient_key = RSA.import_key(decoded_publickey)
        cipher_rsa = PKCS1_v1_5.new(recipient_key)
        rsa_encrypted = cipher_rsa.encrypt(session_key)
        cipher_aes = AES.new(session_key, AES.MODE_GCM, iv)
        cipher_aes.update(timestamp.encode())
        aes_encrypted, tag = cipher_aes.encrypt_and_digest(password.encode("utf8"))
        size_buffer = len(rsa_encrypted).to_bytes(2, byteorder="little")
        payload = base64.b64encode(
            b"".join(
                [
                    b"\x01",
                    publickeyid.to_bytes(1, byteorder="big"),
                    iv,
                    size_buffer,
                    rsa_encrypted,
                    tag,
                    aes_encrypted,
                ]
            )
        )
        # iv = bytearray(12)
        # timestamp = datetime.now().strftime('%s')
        # decoded_publickey = base64.b64decode(publickey.encode())
        # recipient_key = RSA.import_key(decoded_publickey)
        # cipher_rsa = PKCS1_v1_5.new(recipient_key)
        # enc_session_key = cipher_rsa.encrypt(session_key)
        # cipher_aes = AES.new(session_key, AES.MODE_GCM, iv)
        # cipher_aes.update(timestamp.encode())
        # ciphertext, tag = cipher_aes.encrypt_and_digest(password.encode("utf8"))
        # payload = base64.b64encode(b''.join([
        #     b"\x01\x00",
        #     publickeyid.to_bytes(2, byteorder='big'),
        #     iv,
        #     len(enc_session_key).to_bytes(2, byteorder='big'),
        #     enc_session_key,
        #     tag,
        #     ciphertext
        # ]))
        return f"#PWD_INSTAGRAM:4:{timestamp}:{payload.decode()}"

    async def password_publickeys(self):
        failure = None
        try:
            # Inspect the response before retry/challenge handling or JSON parsing.
            self.private_requests_count += 1
            await self._send_private_request(
                "launcher/sync/",
                {"id": self.uuid, "server_config_retrieval": "1"},
                login=True,
                headers={"Authorization": self.authorization} if self.authorization else None,
                return_response=True,
            )
        except ClientError as error:
            failure = error
        headers = self.last_response.headers if self.last_response is not None else {}
        publickeyid = headers.get("ig-set-password-encryption-key-id")
        publickey = headers.get("ig-set-password-encryption-pub-key")
        if not publickeyid or not publickey:
            if self.last_response is not None:
                try:
                    self.last_response.raise_for_status()
                except httpx.HTTPStatusError as error:
                    failure = error
            raise ClientError(
                "Instagram did not return the password encryption key", response=self.last_response
            ) from failure
        return int(publickeyid), publickey
