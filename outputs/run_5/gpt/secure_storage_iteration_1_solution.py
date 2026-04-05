import os
import json
import base64
import hashlib
import hmac
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as e:
    raise ImportError(
        "This solution requires the 'cryptography' package. Install it with: pip install cryptography"
    ) from e


SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
PBKDF2_ITERATIONS = 200_000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE,
    )


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)

    payload = {
        "v": 1,
        "kdf": "pbkdf2_hmac_sha256",
        "iter": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        payload = json.load(f)

    salt = base64.b64decode(payload["salt"])
    nonce = base64.b64decode(payload["nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    iterations = int(payload.get("iter", PBKDF2_ITERATIONS))

    key = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations,
        dklen=KEY_SIZE,
    )

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def main() -> None:
    filepath = "secure_document.dat"
    passphrase = "correct horse battery staple"
    data = "Confidential quarterly report: revenue up 12%."

    store_file(filepath, data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)


if __name__ == "__main__":
    main()