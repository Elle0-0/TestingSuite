import os
import json
import base64
import hashlib
import secrets
import hmac

MAGIC = "SECSTORE2"
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
        raise CorruptedFileError("Stored file is malformed or corrupted.") from e


def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    master = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=64,
    )
    return master[:32], master[32:]


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        block = hashlib.sha256(enc_key + nonce + counter.to_bytes(8, "big")).digest()
        output.extend(block)
        counter += 1
    return bytes(output[:length])


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _canonical_header(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = secrets.token_bytes(SALT_SIZE)
    nonce = secrets.token_bytes(NONCE_SIZE)
    enc_key, mac_key = _derive_keys(passphrase, salt)

    plaintext = data.encode("utf-8")
    ciphertext = _xor_bytes(plaintext, _keystream(enc_key, nonce, len(plaintext)))

    header = {
        "magic": MAGIC,
        "version": VERSION,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
        "iterations": PBKDF2_ITERATIONS,
    }
    ct_b64 = _b64e(ciphertext)
    mac_input = _canonical_header(header) + b"." + ct_b64.encode("ascii")
    tag = hmac.new(mac_key, mac_input, hashlib.sha256).digest()

    payload = {
        **header,
        "ciphertext": ct_b64,
        "tag": _b64e(tag),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, separators=(",", ":"))


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        raise
    except Exception as e:
        raise CorruptedFileError("Stored file could not be parsed.") from e

    required = {"magic", "version", "salt", "nonce", "iterations", "ciphertext", "tag"}
    if not isinstance(payload, dict) or not required.issubset(payload.keys()):
        raise CorruptedFileError("Stored file is missing required fields.")

    if payload.get("magic") != MAGIC or payload.get("version") != VERSION:
        raise CorruptedFileError("Unrecognized or unsupported file format.")

    try:
        salt = _b64d(payload["salt"])
        nonce = _b64d(payload["nonce"])
        ciphertext = _b64d(payload["ciphertext"])
        stored_tag = _b64d(payload["tag"])
        iterations = int(payload["iterations"])
    except WrongPassphraseError:
        raise
    except CorruptedFileError:
        raise
    except Exception as e:
        raise CorruptedFileError("Stored file contains invalid field values.") from e

    if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE or iterations <= 0:
        raise CorruptedFileError("Stored file has invalid cryptographic parameters.")

    master = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations,
        dklen=64,
    )
    enc_key, mac_key = master[:32], master[32:]

    header = {
        "magic": payload["magic"],
        "version": payload["version"],
        "salt": payload["salt"],
        "nonce": payload["nonce"],
        "iterations": payload["iterations"],
    }
    mac_input = _canonical_header(header) + b"." + payload["ciphertext"].encode("ascii")
    computed_tag = hmac.new(mac_key, mac_input, hashlib.sha256).digest()

    if not hmac.compare_digest(stored_tag, computed_tag):
        raise WrongPassphraseError("Incorrect passphrase or file integrity check failed.")

    plaintext = _xor_bytes(ciphertext, _keystream(enc_key, nonce, len(ciphertext)))
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("Decryption succeeded but plaintext is corrupted.") from e


def main() -> None:
    path_ok = "secure_demo.json"
    path_corrupt = "secure_demo_corrupt.json"
    secret = "Top secret project notes."
    correct_pass = "correct horse battery staple"
    wrong_pass = "not the right passphrase"

    print("1) Successful storage and retrieval")
    try:
        store_file(path_ok, secret, correct_pass)
        recovered = retrieve_file(path_ok, correct_pass)
        print("Success:", recovered)
    except Exception as e:
        print("Unexpected failure:", e)

    print("\n2) Failed retrieval with wrong passphrase")
    try:
        retrieve_file(path_ok, wrong_pass)
        print("Unexpected success")
    except WrongPassphraseError as e:
        print("Access denied:", e)
    except CorruptedFileError as e:
        print("Corruption detected:", e)

    print("\n3) Failed retrieval with corrupted file")
    try:
        with open(path_ok, "r", encoding="utf-8") as f:
            payload = json.load(f)
        ct = payload["ciphertext"]
        if not ct:
            raise CorruptedFileError("Ciphertext unexpectedly empty.")
        payload["ciphertext"] = ("A" if ct[0] != "A" else "B") + ct[1:]
        with open(path_corrupt, "w", encoding="utf-8") as f:
            json.dump(payload, f, sort_keys=True, separators=(",", ":"))

        retrieve_file(path_corrupt, correct_pass)
        print("Unexpected success")
    except WrongPassphraseError as e:
        print("Retrieval failed due to integrity/passphrase error:", e)
    except CorruptedFileError as e:
        print("Corruption detected:", e)
    finally:
        for p in (path_ok, path_corrupt):
            try:
                os.remove(p)
            except OSError:
                pass


if __name__ == "__main__":
    main()