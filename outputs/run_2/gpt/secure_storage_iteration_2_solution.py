import os
import json
import base64
import hashlib
import hmac


class SecureStorageError(Exception):
    pass


class InvalidPassphraseError(SecureStorageError):
    pass


class CorruptedFileError(SecureStorageError):
    pass


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    master = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=32)
    enc_key = hashlib.sha256(master + b"enc").digest()
    mac_key = hashlib.sha256(master + b"mac").digest()
    return enc_key, mac_key


def _keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(enc_key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_keys(passphrase, salt)
    plaintext = data.encode("utf-8")
    ciphertext = _xor_bytes(plaintext, _keystream(enc_key, nonce, len(plaintext)))
    mac = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()

    payload = {
        "version": 1,
        "salt": _b64e(salt),
        "nonce": _b64e(nonce),
        "ciphertext": _b64e(ciphertext),
        "mac": _b64e(mac),
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        salt = _b64d(payload["salt"])
        nonce = _b64d(payload["nonce"])
        ciphertext = _b64d(payload["ciphertext"])
        stored_mac = _b64d(payload["mac"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError, base64.binascii.Error) as e:
        raise CorruptedFileError("File is corrupted or unreadable.") from e

    try:
        enc_key, mac_key = _derive_keys(passphrase, salt)
        expected_mac = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(stored_mac, expected_mac):
            raise InvalidPassphraseError("Incorrect passphrase or file integrity check failed.")
        plaintext = _xor_bytes(ciphertext, _keystream(enc_key, nonce, len(ciphertext)))
        return plaintext.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CorruptedFileError("File content is corrupted.") from e


def main() -> None:
    good_path = "secure_demo_ok.dat"
    corrupt_path = "secure_demo_corrupt.dat"
    secret = "Confidential project notes."
    passphrase = "correct horse battery staple"
    wrong_passphrase = "wrong password"

    print("1. Successful storage and retrieval")
    store_file(good_path, secret, passphrase)
    try:
        recovered = retrieve_file(good_path, passphrase)
        print("Success:", recovered)
    except SecureStorageError as e:
        print("Failed:", str(e))

    print("\n2. Failed retrieval with wrong passphrase")
    try:
        retrieve_file(good_path, wrong_passphrase)
        print("Unexpected success")
    except InvalidPassphraseError as e:
        print("Access denied:", str(e))
    except CorruptedFileError as e:
        print("Corruption detected:", str(e))

    print("\n3. Failed retrieval with corrupted file")
    store_file(corrupt_path, secret, passphrase)
    with open(corrupt_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    ct = bytearray(_b64d(payload["ciphertext"]))
    if ct:
        ct[0] ^= 0x01
    else:
        ct = bytearray(b"\x01")
    payload["ciphertext"] = _b64e(bytes(ct))
    with open(corrupt_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    try:
        retrieve_file(corrupt_path, passphrase)
        print("Unexpected success")
    except InvalidPassphraseError as e:
        print("Integrity failure detected:", str(e))
    except CorruptedFileError as e:
        print("Corruption detected:", str(e))


if __name__ == "__main__":
    main()