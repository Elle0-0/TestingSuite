import os
import json
import base64
import hashlib
import hmac
from typing import Tuple

MAGIC = "SSF2"
VERSION = 1
SALT_LEN = 16
ENC_SALT_LEN = 16
IV_LEN = 16
KEY_LEN = 32
PBKDF2_ITERS = 200_000


class SecureStorageError(Exception):
    pass


class InvalidPassphraseError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    try:
        return base64.b64decode(s.encode("ascii"), validate=True)
    except Exception as e:
        raise CorruptedFileError("Invalid base64 encoding in file") from e


def _xor_stream(data: bytes, key: bytes, iv: bytes) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hashlib.sha256(key + iv + counter.to_bytes(8, "big")).digest()
        need = min(len(block), len(data) - len(out))
        start = len(out)
        for i in range(need):
            out.append(data[start + i] ^ block[i])
        counter += 1
    return bytes(out)


def _derive_master_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERS, dklen=KEY_LEN)


def _derive_subkeys(master_key: bytes, enc_salt: bytes) -> Tuple[bytes, bytes]:
    enc_key = hmac.new(master_key, b"enc:" + enc_salt, hashlib.sha256).digest()
    mac_key = hmac.new(master_key, b"mac:" + enc_salt, hashlib.sha256).digest()
    return enc_key, mac_key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_LEN)
    enc_salt = os.urandom(ENC_SALT_LEN)
    iv = os.urandom(IV_LEN)

    master_key = _derive_master_key(passphrase, salt)
    enc_key, mac_key = _derive_subkeys(master_key, enc_salt)

    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream(plaintext, enc_key, iv)

    payload = {
        "magic": MAGIC,
        "version": VERSION,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": PBKDF2_ITERS,
        "salt": _b64e(salt),
        "enc_salt": _b64e(enc_salt),
        "iv": _b64e(iv),
        "ciphertext": _b64e(ciphertext),
    }

    mac_input = (
        payload["magic"].encode("utf-8")
        + str(payload["version"]).encode("utf-8")
        + payload["kdf"].encode("utf-8")
        + str(payload["iterations"]).encode("utf-8")
        + salt
        + enc_salt
        + iv
        + ciphertext
    )
    tag = hmac.new(mac_key, mac_input, hashlib.sha256).digest()
    payload["tag"] = _b64e(tag)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        raise CorruptedFileError("File is not valid JSON") from e
    except OSError as e:
        raise CorruptedFileError("File cannot be read") from e

    required = {"magic", "version", "kdf", "iterations", "salt", "enc_salt", "iv", "ciphertext", "tag"}
    if not isinstance(payload, dict) or not required.issubset(payload.keys()):
        raise CorruptedFileError("File format is invalid or incomplete")

    if payload["magic"] != MAGIC or payload["version"] != VERSION:
        raise CorruptedFileError("Unsupported or invalid file format")

    if payload["kdf"] != "PBKDF2-HMAC-SHA256":
        raise CorruptedFileError("Unsupported key derivation format")

    try:
        iterations = int(payload["iterations"])
    except Exception as e:
        raise CorruptedFileError("Invalid iteration count") from e

    salt = _b64d(payload["salt"])
    enc_salt = _b64d(payload["enc_salt"])
    iv = _b64d(payload["iv"])
    ciphertext = _b64d(payload["ciphertext"])
    tag = _b64d(payload["tag"])

    master_key = _derive_master_key(passphrase, salt)
    enc_key, mac_key = _derive_subkeys(master_key, enc_salt)

    mac_input = (
        payload["magic"].encode("utf-8")
        + str(payload["version"]).encode("utf-8")
        + payload["kdf"].encode("utf-8")
        + str(iterations).encode("utf-8")
        + salt
        + enc_salt
        + iv
        + ciphertext
    )
    expected_tag = hmac.new(mac_key, mac_input, hashlib.sha256).digest()

    if not hmac.compare_digest(tag, expected_tag):
        raise InvalidPassphraseError("Incorrect passphrase or file has been corrupted")

    try:
        plaintext = _xor_stream(ciphertext, enc_key, iv)
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("Decryption succeeded but plaintext is invalid") from e


def main() -> None:
    ok_path = "secure_demo_ok.ssf"
    bad_path = "secure_demo_corrupt.ssf"
    secret = "Confidential project notes: launch at 09:00."
    passphrase = "correct horse battery staple"
    wrong_passphrase = "totally wrong passphrase"

    store_file(ok_path, secret, passphrase)
    print("Stored file successfully.")

    try:
        recovered = retrieve_file(ok_path, passphrase)
        print("Successful retrieval:", recovered)
    except SecureStorageError as e:
        print("Unexpected failure during valid retrieval:", str(e))

    try:
        retrieve_file(ok_path, wrong_passphrase)
        print("Unexpected success with wrong passphrase.")
    except InvalidPassphraseError as e:
        print("Wrong passphrase detected:", str(e))
    except CorruptedFileError as e:
        print("Corruption detected during wrong-passphrase test:", str(e))

    store_file(bad_path, secret, passphrase)
    with open(bad_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    ct = bytearray(base64.b64decode(payload["ciphertext"]))
    if ct:
        ct[0] ^= 0x01
    else:
        ct = bytearray(b"\x00")
    payload["ciphertext"] = base64.b64encode(bytes(ct)).decode("ascii")
    with open(bad_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    try:
        retrieve_file(bad_path, passphrase)
        print("Unexpected success with corrupted file.")
    except InvalidPassphraseError as e:
        print("Corrupted file detected:", str(e))
    except CorruptedFileError as e:
        print("Corrupted file detected:", str(e))


if __name__ == "__main__":
    main()