import os
import base64
import hashlib
from typing import Optional

MAGIC = b"SECSTORE1"
SALT_SIZE = 16
NONCE_SIZE = 16
KEYSTREAM_BLOCK = 32


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def _derive_key(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=length)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _encrypt(plaintext: bytes, passphrase: str) -> bytes:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    stream = _keystream(key, nonce, len(plaintext))
    ciphertext = _xor_bytes(plaintext, stream)
    check = hashlib.sha256(key + b"verify").digest()
    payload = MAGIC + salt + nonce + check + ciphertext
    return base64.b64encode(payload)


def _decrypt(blob: bytes, passphrase: str) -> str:
    payload = base64.b64decode(blob)
    header_len = len(MAGIC) + SALT_SIZE + NONCE_SIZE + 32
    if len(payload) < header_len or payload[: len(MAGIC)] != MAGIC:
        raise ValueError("Invalid file format")
    offset = len(MAGIC)
    salt = payload[offset : offset + SALT_SIZE]
    offset += SALT_SIZE
    nonce = payload[offset : offset + NONCE_SIZE]
    offset += NONCE_SIZE
    stored_check = payload[offset : offset + 32]
    offset += 32
    ciphertext = payload[offset:]
    key = _derive_key(passphrase, salt)
    check = hashlib.sha256(key + b"verify").digest()
    if check != stored_check:
        raise ValueError("Incorrect passphrase")
    stream = _keystream(key, nonce, len(ciphertext))
    plaintext = _xor_bytes(ciphertext, stream)
    return plaintext.decode("utf-8")


def store_file(filepath: str, data: str, passphrase: str) -> None:
    encrypted = _encrypt(data.encode("utf-8"), passphrase)
    with open(filepath, "wb") as f:
        f.write(encrypted)


def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        blob = f.read()
    return _decrypt(blob, passphrase)


def main() -> None:
    filepath = "secure_sample.dat"
    document = "Confidential corporate report: Q4 acquisition strategy."
    passphrase = "correct horse battery staple"

    store_file(filepath, document, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)


if __name__ == "__main__":
    main()