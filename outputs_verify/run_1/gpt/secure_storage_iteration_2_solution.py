import os
import json
import base64
import hashlib
import hmac
from typing import Tuple

SALT_SIZE = 16
KEY_LEN = 32
PBKDF2_ITERATIONS = 200_000
NONCE_SIZE = 32


class SecureStorageError(Exception):
    pass


class AuthenticationError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


def _derive_keys(passphrase: str, salt: bytes) -> Tuple[bytes, bytes]:
    master = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_LEN * 2,
    )
    return master[:KEY_LEN], master[KEY_LEN:]


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(
            enc_key,
            nonce + counter.to_bytes(8, "big"),
            hashlib.sha256,
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    enc_key, mac_key = _derive_keys(passphrase, salt)

    plaintext = data.encode("utf-8")
    stream = _keystream(enc_key, nonce, len(plaintext))
    ciphertext = _xor_bytes(plaintext, stream)

    mac_data = salt + nonce + ciphertext
    tag = hmac.new(mac_key, mac_data, hashlib.sha256).digest()

    payload = {
        "version": 1,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise CorruptedFileError("File is unreadable or malformed") from e

    try:
        salt = base64.b64decode(payload["salt"], validate=True)
        nonce = base64.b64decode(payload["nonce"], validate=True)
        ciphertext = base64.b64decode(payload["ciphertext"], validate=True)
        stored_tag = base64.b64decode(payload["tag"], validate=True)
        iterations = int(payload["iterations"])
    except (KeyError, ValueError, TypeError) as e:
        raise CorruptedFileError("File metadata is invalid") from e

    if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE or len(stored_tag) != 32:
        raise CorruptedFileError("File structure is invalid")

    enc_key, mac_key = _derive_keys(passphrase, salt)
    expected_tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()

    if not hmac.compare_digest(stored_tag, expected_tag):
        raise AuthenticationError("Wrong passphrase or file has been tampered with")

    try:
        stream = _keystream(enc_key, nonce, len(ciphertext))
        plaintext = _xor_bytes(ciphertext, stream)
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("Decryption succeeded but plaintext is corrupted") from e


def main() -> None:
    good_path = "secure_demo.dat"
    corrupt_path = "secure_demo_corrupt.dat"
    data = "Confidential message: launch at dawn."
    correct_passphrase = "correct horse battery staple"
    wrong_passphrase = "totally wrong passphrase"

    print("1. Successful storage and retrieval")
    store_file(good_path, data, correct_passphrase)
    try:
        recovered = retrieve_file(good_path, correct_passphrase)
        print("Success:", recovered)
    except SecureStorageError as e:
        print("Failed:", str(e))

    print("\n2. Failed retrieval with wrong passphrase")
    try:
        retrieve_file(good_path, wrong_passphrase)
        print("Unexpected success")
    except AuthenticationError as e:
        print("Access denied:", str(e))
    except SecureStorageError as e:
        print("Failed:", str(e))

    print("\n3. Failed retrieval with corrupted file")
    store_file(corrupt_path, data, correct_passphrase)
    with open(corrupt_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    corrupted_ct = bytearray(base64.b64decode(payload["ciphertext"]))
    if corrupted_ct:
        corrupted_ct[0] ^= 0x01
    else:
        corrupted_ct = bytearray(b"\x00")
    payload["ciphertext"] = base64.b64encode(bytes(corrupted_ct)).decode("ascii")

    with open(corrupt_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    try:
        retrieve_file(corrupt_path, correct_passphrase)
        print("Unexpected success")
    except AuthenticationError as e:
        print("Integrity check failed:", str(e))
    except SecureStorageError as e:
        print("Failed:", str(e))


if __name__ == "__main__":
    main()