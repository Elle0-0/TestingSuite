import base64
import hashlib
import hmac
import json
import os
import secrets
from typing import Tuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecureStorageError(Exception):
    pass


class WrongPassphraseError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


_MAGIC = "SECSTORE2"
_VERSION = 1
_SALT_LEN = 16
_NONCE_LEN = 12
_KEY_LEN = 32
_PBKDF2_ITERATIONS = 200_000


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=_KEY_LEN,
    )


def _canonical_header(doc: dict) -> bytes:
    header = {
        "magic": doc["magic"],
        "version": doc["version"],
        "kdf": doc["kdf"],
        "iter": doc["iter"],
        "salt": doc["salt"],
        "nonce": doc["nonce"],
    }
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = secrets.token_bytes(_SALT_LEN)
    nonce = secrets.token_bytes(_NONCE_LEN)
    key = _derive_key(passphrase, salt)

    doc = {
        "magic": _MAGIC,
        "version": _VERSION,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iter": _PBKDF2_ITERATIONS,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
    }

    aad = _canonical_header(doc)
    ciphertext = AESGCM(key).encrypt(nonce, data.encode("utf-8"), aad)
    doc["ciphertext"] = _b64e(ciphertext)

    serialized = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(serialized)


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
    except FileNotFoundError:
        raise

    try:
        doc = json.loads(raw)
        if not isinstance(doc, dict):
            raise CorruptedFileError("Stored file is not a valid object")
        required = {"magic", "version", "kdf", "iter", "salt", "nonce", "ciphertext"}
        if set(doc.keys()) != required:
            raise CorruptedFileError("Stored file structure is invalid")
        if doc["magic"] != _MAGIC or doc["version"] != _VERSION:
            raise CorruptedFileError("Unsupported or invalid file format")
        if doc["kdf"] != "PBKDF2-HMAC-SHA256":
            raise CorruptedFileError("Unsupported key derivation format")
        if not isinstance(doc["iter"], int) or doc["iter"] <= 0:
            raise CorruptedFileError("Invalid iteration count")

        salt = _b64d(doc["salt"])
        nonce = _b64d(doc["nonce"])
        ciphertext = _b64d(doc["ciphertext"])

        if len(salt) != _SALT_LEN or len(nonce) != _NONCE_LEN or len(ciphertext) < 16:
            raise CorruptedFileError("Stored file contains invalid binary fields")

        key = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            salt,
            doc["iter"],
            dklen=_KEY_LEN,
        )
        aad = _canonical_header(doc)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        return plaintext.decode("utf-8")
    except WrongPassphraseError:
        raise
    except CorruptedFileError:
        raise
    except (json.JSONDecodeError, ValueError, TypeError, UnicodeDecodeError) as e:
        raise CorruptedFileError("Stored file is corrupted or malformed") from e
    except InvalidTag as e:
        try:
            with open(filepath, "rb") as f:
                file_bytes = f.read()
            digest = hashlib.sha256(file_bytes).digest()
            marker = hmac.new(b"format-check", file_bytes, hashlib.sha256).digest()
            if len(file_bytes) == 0 or digest == marker:
                raise CorruptedFileError("Stored file is corrupted") from e
        except OSError:
            pass
        raise WrongPassphraseError("Wrong passphrase or corrupted file") from e


def main() -> None:
    good_path = "secure_demo_good.json"
    corrupted_path = "secure_demo_corrupted.json"
    secret = "Confidential document contents."
    correct_passphrase = "correct horse battery staple"
    wrong_passphrase = "incorrect passphrase"

    print("1) Successful storage and retrieval")
    try:
        store_file(good_path, secret, correct_passphrase)
        recovered = retrieve_file(good_path, correct_passphrase)
        print(f"Success: retrieved data = {recovered!r}")
    except Exception as e:
        print(f"Unexpected failure: {type(e).__name__}: {e}")

    print("\n2) Failed retrieval with wrong passphrase")
    try:
        retrieve_file(good_path, wrong_passphrase)
        print("Unexpected success with wrong passphrase")
    except WrongPassphraseError:
        print("Access denied: wrong passphrase (or authentication failed).")
    except CorruptedFileError:
        print("Access denied: file is corrupted.")
    except Exception as e:
        print(f"Unexpected failure: {type(e).__name__}: {e}")

    print("\n3) Failed retrieval with corrupted file")
    try:
        store_file(corrupted_path, secret, correct_passphrase)
        with open(corrupted_path, "rb") as f:
            content = bytearray(f.read())
        if content:
            idx = len(content) // 2
            content[idx] ^= 0x01
        with open(corrupted_path, "wb") as f:
            f.write(content)

        retrieve_file(corrupted_path, correct_passphrase)
        print("Unexpected success retrieving corrupted file")
    except WrongPassphraseError:
        print("Access denied: wrong passphrase (or authentication failed).")
    except CorruptedFileError:
        print("Retrieval failed: file corruption detected.")
    except Exception as e:
        print(f"Unexpected failure: {type(e).__name__}: {e}")
    finally:
        for path in (good_path, corrupted_path):
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == "__main__":
    main()