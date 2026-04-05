import os
import json
import base64
import hashlib
import hmac
from typing import Tuple

MAGIC = "SSF2"
VERSION = 1
SALT_SIZE = 16
NONCE_SIZE = 16
KEY_LEN = 32
PBKDF2_ITERATIONS = 200_000


class SecureStorageError(Exception):
    pass


class WrongPassphraseError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    try:
        return base64.b64decode(data.encode("ascii"), validate=True)
    except Exception as e:
        raise CorruptedFileError("Invalid base64 encoding in stored file") from e


def _derive_keys(passphrase: str, salt: bytes) -> Tuple[bytes, bytes]:
    master = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_LEN * 2,
    )
    return master[:KEY_LEN], master[KEY_LEN:]


def _keystream_block(enc_key: bytes, nonce: bytes, counter: int) -> bytes:
    return hashlib.sha256(enc_key + nonce + counter.to_bytes(8, "big")).digest()


def _xor_stream_encrypt(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    idx = 0
    while idx < len(data):
        block = _keystream_block(enc_key, nonce, counter)
        chunk = data[idx:idx + len(block)]
        out.extend(bytes(a ^ b for a, b in zip(chunk, block)))
        idx += len(chunk)
        counter += 1
    return bytes(out)


def _compute_tag(mac_key: bytes, header: bytes, ciphertext: bytes) -> bytes:
    return hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    enc_key, mac_key = _derive_keys(passphrase, salt)

    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream_encrypt(plaintext, enc_key, nonce)

    header_obj = {
        "magic": MAGIC,
        "version": VERSION,
        "kdf": "pbkdf2_hmac_sha256",
        "iterations": PBKDF2_ITERATIONS,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
    }
    header_bytes = json.dumps(header_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tag = _compute_tag(mac_key, header_bytes, ciphertext)

    file_obj = {
        "header": header_obj,
        "ciphertext": _b64e(ciphertext),
        "tag": _b64e(tag),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(file_obj, f, sort_keys=True, separators=(",", ":"))


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            file_obj = json.load(f)
    except json.JSONDecodeError as e:
        raise CorruptedFileError("Stored file is not valid JSON") from e
    except OSError:
        raise

    if not isinstance(file_obj, dict):
        raise CorruptedFileError("Stored file format is invalid")

    if "header" not in file_obj or "ciphertext" not in file_obj or "tag" not in file_obj:
        raise CorruptedFileError("Stored file is missing required fields")

    header = file_obj["header"]
    if not isinstance(header, dict):
        raise CorruptedFileError("Header format is invalid")

    if header.get("magic") != MAGIC or header.get("version") != VERSION:
        raise CorruptedFileError("Unsupported or invalid file format")

    if header.get("kdf") != "pbkdf2_hmac_sha256":
        raise CorruptedFileError("Unsupported key derivation function")

    iterations = header.get("iterations")
    if not isinstance(iterations, int) or iterations <= 0:
        raise CorruptedFileError("Invalid iteration count")

    salt = _b64d(header.get("salt", ""))
    nonce = _b64d(header.get("nonce", ""))
    ciphertext = _b64d(file_obj.get("ciphertext", ""))
    stored_tag = _b64d(file_obj.get("tag", ""))

    enc_key, mac_key = _derive_keys(passphrase, salt)
    header_bytes = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    computed_tag = _compute_tag(mac_key, header_bytes, ciphertext)

    if not hmac.compare_digest(stored_tag, computed_tag):
        raise WrongPassphraseError("Wrong passphrase or file integrity check failed")

    try:
        plaintext = _xor_stream_encrypt(ciphertext, enc_key, nonce)
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("Decryption succeeded but plaintext is corrupted") from e


def main() -> None:
    good_path = "secure_demo.json"
    corrupted_path = "secure_demo_corrupted.json"
    passphrase = "correct horse battery staple"
    wrong_passphrase = "incorrect passphrase"
    data = "Confidential project notes: launch at 09:00."

    print("1. Successful storage and retrieval")
    try:
        store_file(good_path, data, passphrase)
        recovered = retrieve_file(good_path, passphrase)
        print("Success:", recovered)
    except Exception as e:
        print("Unexpected failure:", str(e))

    print("\n2. Failed retrieval with wrong passphrase")
    try:
        retrieve_file(good_path, wrong_passphrase)
        print("Unexpected success")
    except WrongPassphraseError as e:
        print("Access denied:", str(e))
    except CorruptedFileError as e:
        print("Corruption detected:", str(e))
    except Exception as e:
        print("Unexpected failure:", str(e))

    print("\n3. Failed retrieval with corrupted file")
    try:
        with open(good_path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        ct = bytearray(base64.b64decode(obj["ciphertext"].encode("ascii")))
        if len(ct) == 0:
            ct = bytearray(b"\x00")
        ct[0] ^= 0x01
        obj["ciphertext"] = base64.b64encode(bytes(ct)).decode("ascii")
        with open(corrupted_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, sort_keys=True, separators=(",", ":"))

        retrieve_file(corrupted_path, passphrase)
        print("Unexpected success")
    except WrongPassphraseError as e:
        print("Integrity failure detected:", str(e))
    except CorruptedFileError as e:
        print("Corruption detected:", str(e))
    except Exception as e:
        print("Unexpected failure:", str(e))


if __name__ == "__main__":
    main()