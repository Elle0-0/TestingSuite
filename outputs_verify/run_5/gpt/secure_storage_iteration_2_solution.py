import os
import json
import base64
import hashlib
import hmac
from typing import Tuple

MAGIC = "SSF2"
VERSION = 1
SALT_SIZE = 16
ENC_SALT_SIZE = 16
NONCE_SIZE = 16
KEY_SIZE = 32
PBKDF2_ITERATIONS = 200_000


class SecureStorageError(Exception):
    pass


class InvalidPassphraseError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    pos = 0
    while pos < len(data):
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        take = min(len(block), len(data) - pos)
        for i in range(take):
            out.append(data[pos + i] ^ block[i])
        pos += take
        counter += 1
    return bytes(out)


def _derive_master_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE,
    )


def _expand_keys(master_key: bytes, enc_salt: bytes) -> Tuple[bytes, bytes]:
    enc_key = hmac.new(master_key, b"enc:" + enc_salt, hashlib.sha256).digest()
    mac_key = hmac.new(master_key, b"mac:" + enc_salt, hashlib.sha256).digest()
    return enc_key, mac_key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    enc_salt = os.urandom(ENC_SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)

    master_key = _derive_master_key(passphrase, salt)
    enc_key, mac_key = _expand_keys(master_key, enc_salt)

    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream(plaintext, enc_key, nonce)

    header = {
        "magic": MAGIC,
        "version": VERSION,
        "iterations": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "enc_salt": base64.b64encode(enc_salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }

    mac_payload = (
        header["magic"].encode("utf-8")
        + b"|"
        + str(header["version"]).encode("ascii")
        + b"|"
        + str(header["iterations"]).encode("ascii")
        + b"|"
        + salt
        + b"|"
        + enc_salt
        + b"|"
        + nonce
        + b"|"
        + ciphertext
    )
    tag = hmac.new(mac_key, mac_payload, hashlib.sha256).digest()
    header["tag"] = base64.b64encode(tag).decode("ascii")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(header, f)


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise CorruptedFileError("File is unreadable or corrupted") from e

    try:
        if obj.get("magic") != MAGIC or obj.get("version") != VERSION:
            raise CorruptedFileError("File format is invalid or unsupported")

        iterations = int(obj["iterations"])
        salt = base64.b64decode(obj["salt"], validate=True)
        enc_salt = base64.b64decode(obj["enc_salt"], validate=True)
        nonce = base64.b64decode(obj["nonce"], validate=True)
        ciphertext = base64.b64decode(obj["ciphertext"], validate=True)
        tag = base64.b64decode(obj["tag"], validate=True)
    except (KeyError, ValueError, TypeError) as e:
        raise CorruptedFileError("File metadata is corrupted") from e

    master_key = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations,
        dklen=KEY_SIZE,
    )
    enc_key, mac_key = _expand_keys(master_key, enc_salt)

    mac_payload = (
        MAGIC.encode("utf-8")
        + b"|"
        + str(VERSION).encode("ascii")
        + b"|"
        + str(iterations).encode("ascii")
        + b"|"
        + salt
        + b"|"
        + enc_salt
        + b"|"
        + nonce
        + b"|"
        + ciphertext
    )
    expected_tag = hmac.new(mac_key, mac_payload, hashlib.sha256).digest()

    if not hmac.compare_digest(tag, expected_tag):
        raise InvalidPassphraseError("Wrong passphrase or file has been tampered with")

    plaintext = _xor_stream(ciphertext, enc_key, nonce)
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("Decryption succeeded but content is corrupted") from e


def main() -> None:
    good_path = "demo_secure_file.json"
    corrupted_path = "demo_secure_file_corrupted.json"
    passphrase = "correct horse battery staple"
    wrong_passphrase = "not the right secret"
    content = "Sensitive report: launch code is 12345."

    print("1) Successful storage and retrieval")
    store_file(good_path, content, passphrase)
    try:
        recovered = retrieve_file(good_path, passphrase)
        print("Success:", recovered)
    except SecureStorageError as e:
        print("Unexpected failure:", str(e))

    print("\n2) Failed retrieval with wrong passphrase")
    try:
        retrieve_file(good_path, wrong_passphrase)
        print("Unexpected success")
    except InvalidPassphraseError:
        print("Failed as expected: wrong passphrase or file tampering detected")
    except CorruptedFileError:
        print("Failed: file is corrupted")
    except SecureStorageError as e:
        print("Failed with secure storage error:", str(e))

    print("\n3) Failed retrieval with corrupted file")
    with open(good_path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    ct = bytearray(base64.b64decode(obj["ciphertext"]))
    if ct:
        ct[0] ^= 0x01
    obj["ciphertext"] = base64.b64encode(bytes(ct)).decode("ascii")

    with open(corrupted_path, "w", encoding="utf-8") as f:
        json.dump(obj, f)

    try:
        retrieve_file(corrupted_path, passphrase)
        print("Unexpected success")
    except InvalidPassphraseError:
        print("Failed as expected: file corruption or tampering detected")
    except CorruptedFileError:
        print("Failed: file is corrupted")
    except SecureStorageError as e:
        print("Failed with secure storage error:", str(e))


if __name__ == "__main__":
    main()