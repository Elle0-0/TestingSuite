import os
import json
import base64
import hashlib
import hmac
from typing import Tuple

SALT_SIZE = 16
NONCE_SIZE = 16
KEY_LEN = 32
PBKDF2_ITERATIONS = 200_000


class SecureStorageError(Exception):
    pass


class InvalidPassphraseError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _keystream_block(enc_key: bytes, nonce: bytes, counter: int) -> bytes:
    return hashlib.sha256(enc_key + nonce + counter.to_bytes(8, "big")).digest()


def _stream_cipher_crypt(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    for i in range(0, len(data), 32):
        block = data[i:i + 32]
        ks = _keystream_block(enc_key, nonce, counter)
        out.extend(_xor_bytes(block, ks[:len(block)]))
        counter += 1
    return bytes(out)


def _derive_keys(passphrase: str, salt: bytes) -> Tuple[bytes, bytes]:
    master = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=64,
    )
    return master[:32], master[32:]


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    enc_key, mac_key = _derive_keys(passphrase, salt)

    plaintext = data.encode("utf-8")
    ciphertext = _stream_cipher_crypt(plaintext, enc_key, nonce)

    header = {
        "v": 1,
        "kdf": "pbkdf2_hmac_sha256",
        "iter": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ct": base64.b64encode(ciphertext).decode("ascii"),
    }

    signed = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tag = hmac.new(mac_key, signed, hashlib.sha256).digest()
    header["tag"] = base64.b64encode(tag).decode("ascii")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(header, f, sort_keys=True, separators=(",", ":"))


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        raise CorruptedFileError("File is unreadable or not valid structured data.") from e

    try:
        salt = base64.b64decode(payload["salt"], validate=True)
        nonce = base64.b64decode(payload["nonce"], validate=True)
        ciphertext = base64.b64decode(payload["ct"], validate=True)
        stored_tag = base64.b64decode(payload["tag"], validate=True)
        iterations = int(payload["iter"])
    except Exception as e:
        raise CorruptedFileError("File metadata is malformed or incomplete.") from e

    if (
        payload.get("v") != 1
        or payload.get("kdf") != "pbkdf2_hmac_sha256"
        or len(salt) != SALT_SIZE
        or len(nonce) != NONCE_SIZE
        or iterations <= 0
    ):
        raise CorruptedFileError("File format is invalid or unsupported.")

    master = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations,
        dklen=64,
    )
    enc_key, mac_key = master[:32], master[32:]

    signed_fields = {
        "ct": payload["ct"],
        "iter": payload["iter"],
        "kdf": payload["kdf"],
        "nonce": payload["nonce"],
        "salt": payload["salt"],
        "v": payload["v"],
    }
    signed = json.dumps(signed_fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_tag = hmac.new(mac_key, signed, hashlib.sha256).digest()

    if not hmac.compare_digest(stored_tag, expected_tag):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            if b'"tag"' not in raw or b'"ct"' not in raw or b'"salt"' not in raw or b'"nonce"' not in raw:
                raise CorruptedFileError("File appears corrupted or incomplete.")
        except CorruptedFileError:
            raise
        except Exception:
            pass
        raise InvalidPassphraseError("Incorrect passphrase or authentication failed.")

    plaintext = _stream_cipher_crypt(ciphertext, enc_key, nonce)
    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("Decryption succeeded but content is corrupted.") from e


def main() -> None:
    good_path = "secure_demo.json"
    corrupt_path = "secure_demo_corrupt.json"
    secret = "Top secret project notes."
    correct_passphrase = "correct horse battery staple"
    wrong_passphrase = "not the right passphrase"

    try:
        store_file(good_path, secret, correct_passphrase)
        print("Stored file successfully.")

        recovered = retrieve_file(good_path, correct_passphrase)
        print("Successful retrieval:", recovered)

        try:
            retrieve_file(good_path, wrong_passphrase)
            print("Wrong passphrase test: unexpected success")
        except InvalidPassphraseError as e:
            print("Wrong passphrase test:", str(e))
        except CorruptedFileError as e:
            print("Wrong passphrase test reported corruption:", str(e))

        with open(good_path, "rb") as f:
            content = bytearray(f.read())

        if content:
            idx = len(content) // 2
            content[idx] ^= 0x01

        with open(corrupt_path, "wb") as f:
            f.write(content)

        try:
            retrieve_file(corrupt_path, correct_passphrase)
            print("Corrupted file test: unexpected success")
        except CorruptedFileError as e:
            print("Corrupted file test:", str(e))
        except InvalidPassphraseError as e:
            print("Corrupted file test reported wrong passphrase:", str(e))
    finally:
        for path in (good_path, corrupt_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


if __name__ == "__main__":
    main()