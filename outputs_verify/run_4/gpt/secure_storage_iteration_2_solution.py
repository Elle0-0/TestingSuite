import os
import json
import base64
import hashlib
import hmac

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as e:
    raise ImportError("This solution requires the 'cryptography' package.") from e


class SecureStorageError(Exception):
    pass


class AuthenticationError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


MAGIC = "SECSTORE_V2"
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
PBKDF2_ITERATIONS = 200_000


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE,
    )


def _aad_from_header(payload: dict) -> bytes:
    header = {
        "magic": payload["magic"],
        "kdf": payload["kdf"],
        "iterations": payload["iterations"],
        "salt": payload["salt"],
        "nonce": payload["nonce"],
    }
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)

    payload = {
        "magic": MAGIC,
        "kdf": "pbkdf2_hmac_sha256",
        "iterations": PBKDF2_ITERATIONS,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
    }

    aad = _aad_from_header(payload)
    ciphertext = AESGCM(key).encrypt(nonce, data.encode("utf-8"), aad)
    payload["ciphertext"] = _b64e(ciphertext)

    temp_path = filepath + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, separators=(",", ":"))
    os.replace(temp_path, filepath)


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise CorruptedFileError("File is unreadable or not valid storage format.") from e

    required_fields = {"magic", "kdf", "iterations", "salt", "nonce", "ciphertext"}
    if not isinstance(payload, dict) or not required_fields.issubset(payload.keys()):
        raise CorruptedFileError("File is missing required fields.")

    if payload.get("magic") != MAGIC:
        raise CorruptedFileError("Unrecognized file format.")
    if payload.get("kdf") != "pbkdf2_hmac_sha256":
        raise CorruptedFileError("Unsupported key derivation configuration.")
    if not isinstance(payload.get("iterations"), int) or payload["iterations"] <= 0:
        raise CorruptedFileError("Invalid KDF iteration count.")

    try:
        salt = _b64d(payload["salt"])
        nonce = _b64d(payload["nonce"])
        ciphertext = _b64d(payload["ciphertext"])
    except Exception as e:
        raise CorruptedFileError("File contains invalid encoded data.") from e

    if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE or len(ciphertext) < 16:
        raise CorruptedFileError("File contains invalid cryptographic parameters.")

    key = _derive_key(passphrase, salt)
    aad = _aad_from_header(payload)

    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        return plaintext.decode("utf-8")
    except Exception:
        if hmac.compare_digest(_derive_key(passphrase, salt), key):
            raise AuthenticationError("Wrong passphrase or file integrity check failed.")
        raise AuthenticationError("Wrong passphrase or file integrity check failed.")


def main() -> None:
    good_path = "demo_secure_store.json"
    bad_path = "demo_secure_store_corrupt.json"
    passphrase = "correct horse battery staple"
    wrong_passphrase = "not the right passphrase"
    data = "Sensitive document contents."

    print("1) Successful storage and retrieval")
    store_file(good_path, data, passphrase)
    try:
        recovered = retrieve_file(good_path, passphrase)
        print("Success:", recovered)
    except SecureStorageError as e:
        print("Failed:", str(e))

    print("\n2) Failed retrieval with wrong passphrase")
    try:
        retrieve_file(good_path, wrong_passphrase)
        print("Unexpected success")
    except AuthenticationError as e:
        print("Access denied:", str(e))
    except CorruptedFileError as e:
        print("Corruption detected:", str(e))

    print("\n3) Failed retrieval with corrupted file")
    with open(good_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    ct = bytearray(_b64d(payload["ciphertext"]))
    if ct:
        ct[0] ^= 0x01
    payload["ciphertext"] = _b64e(bytes(ct))

    with open(bad_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, separators=(",", ":"))

    try:
        retrieve_file(bad_path, passphrase)
        print("Unexpected success")
    except AuthenticationError as e:
        print("Retrieval failed:", str(e))
    except CorruptedFileError as e:
        print("Corruption detected:", str(e))


if __name__ == "__main__":
    main()