import os
import json
import base64
import hashlib
import hmac
from typing import Tuple

_MAGIC = "SSF2"
_VERSION = 1
_SALT_SIZE = 16
_NONCE_SIZE = 16
_KEY_LEN = 32
_PBKDF2_ITERS = 200_000


class SecureStorageError(Exception):
    pass


class InvalidPassphraseError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _kdf(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERS, dklen=_KEY_LEN)


def _keystream_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    return hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()


def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    i = 0
    while i < len(data):
        block = _keystream_block(key, nonce, counter)
        chunk = data[i:i + len(block)]
        out.extend(a ^ b for a, b in zip(chunk, block))
        i += len(chunk)
        counter += 1
    return bytes(out)


def _derive_keys(passphrase: str, salt: bytes) -> Tuple[bytes, bytes]:
    master = _kdf(passphrase, salt)
    enc_key = hmac.new(master, b"enc", hashlib.sha256).digest()
    mac_key = hmac.new(master, b"mac", hashlib.sha256).digest()
    return enc_key, mac_key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    enc_key, mac_key = _derive_keys(passphrase, salt)
    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream(plaintext, enc_key, nonce)

    aad_obj = {
        "magic": _MAGIC,
        "version": _VERSION,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
        "iterations": _PBKDF2_ITERS,
    }
    aad = json.dumps(aad_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tag = hmac.new(mac_key, aad + ciphertext, hashlib.sha256).digest()

    obj = {
        **aad_obj,
        "ciphertext": _b64e(ciphertext),
        "tag": _b64e(tag),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(obj, f, sort_keys=True, separators=(",", ":"))


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise CorruptedFileError("File is unreadable or not valid storage format") from e

    required = {"magic", "version", "salt", "nonce", "iterations", "ciphertext", "tag"}
    if not isinstance(obj, dict) or not required.issubset(obj.keys()):
        raise CorruptedFileError("File is missing required fields")

    if obj.get("magic") != _MAGIC or obj.get("version") != _VERSION:
        raise CorruptedFileError("Unsupported or invalid file format")

    try:
        salt = _b64d(obj["salt"])
        nonce = _b64d(obj["nonce"])
        ciphertext = _b64d(obj["ciphertext"])
        tag = _b64d(obj["tag"])
        iterations = int(obj["iterations"])
    except Exception as e:
        raise CorruptedFileError("File contains invalid encoded data") from e

    if len(salt) != _SALT_SIZE or len(nonce) != _NONCE_SIZE or iterations != _PBKDF2_ITERS:
        raise CorruptedFileError("File metadata is invalid")

    enc_key, mac_key = _derive_keys(passphrase, salt)
    aad_obj = {
        "magic": obj["magic"],
        "version": obj["version"],
        "salt": obj["salt"],
        "nonce": obj["nonce"],
        "iterations": obj["iterations"],
    }
    aad = json.dumps(aad_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_tag = hmac.new(mac_key, aad + ciphertext, hashlib.sha256).digest()

    if not hmac.compare_digest(tag, expected_tag):
        raise InvalidPassphraseError("Incorrect passphrase or file integrity check failed")

    plaintext = _xor_stream(ciphertext, enc_key, nonce)
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("Decrypted data is not valid text") from e


def main() -> None:
    good_path = "secure_demo_good.ssf"
    bad_path = "secure_demo_corrupt.ssf"
    secret = "Confidential report: launch at 09:00."
    passphrase = "correct horse battery staple"
    wrong_passphrase = "totally wrong password"

    for p in (good_path, bad_path):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass

    print("Storing file...")
    store_file(good_path, secret, passphrase)
    print("Stored successfully.")

    print("\nRetrieving with correct passphrase...")
    try:
        recovered = retrieve_file(good_path, passphrase)
        print("Success:", recovered)
    except SecureStorageError as e:
        print("Failed:", str(e))

    print("\nRetrieving with wrong passphrase...")
    try:
        retrieve_file(good_path, wrong_passphrase)
        print("Unexpected success")
    except InvalidPassphraseError:
        print("Failed: incorrect passphrase or integrity verification failed.")
    except CorruptedFileError as e:
        print("Failed due to corruption:", str(e))

    with open(good_path, "rb") as src:
        content = bytearray(src.read())
    if content:
        idx = len(content) // 2
        content[idx] ^= 0x01
    with open(bad_path, "wb") as dst:
        dst.write(content)

    print("\nRetrieving corrupted file...")
    try:
        retrieve_file(bad_path, passphrase)
        print("Unexpected success")
    except InvalidPassphraseError:
        print("Failed: corrupted file detected (integrity verification failed).")
    except CorruptedFileError as e:
        print("Failed: corrupted file detected.", str(e))


if __name__ == "__main__":
    main()