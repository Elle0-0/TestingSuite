import os
import json
import base64
import hashlib
import secrets

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as e:
    raise ImportError("This solution requires the 'cryptography' package.") from e


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)

    payload = {
        "v": 1,
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

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def main() -> None:
    filepath = "secure_document.enc"
    sample_data = "Confidential corporate document: Q3 acquisition strategy."
    passphrase = "correct horse battery staple"

    store_file(filepath, sample_data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)

    try:
        os.remove(filepath)
    except OSError:
        pass


if __name__ == "__main__":
    main()