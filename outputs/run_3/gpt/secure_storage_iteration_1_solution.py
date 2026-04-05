import os
import base64
import hashlib
from typing import Optional

MAGIC = b"SSF1"
SALT_SIZE = 16
NONCE_SIZE = 16
KEY_SIZE = 32
PBKDF2_ITERATIONS = 200_000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
        dklen=KEY_SIZE,
    )


def _keystream_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    return hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()


def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    i = 0
    while i < len(data):
        block = _keystream_block(key, nonce, counter)
        chunk = data[i:i + len(block)]
        out.extend(bytes(a ^ b for a, b in zip(chunk, block)))
        i += len(block)
        counter += 1
    return bytes(out)


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream(plaintext, key, nonce)
    payload = MAGIC + salt + nonce + ciphertext
    encoded = base64.b64encode(payload)
    with open(filepath, "wb") as f:
        f.write(encoded)


def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        encoded = f.read()
    payload = base64.b64decode(encoded)
    if len(payload) < len(MAGIC) + SALT_SIZE + NONCE_SIZE or payload[:len(MAGIC)] != MAGIC:
        raise ValueError("Invalid file format")
    offset = len(MAGIC)
    salt = payload[offset:offset + SALT_SIZE]
    offset += SALT_SIZE
    nonce = payload[offset:offset + NONCE_SIZE]
    offset += NONCE_SIZE
    ciphertext = payload[offset:]
    key = _derive_key(passphrase, salt)
    plaintext = _xor_stream(ciphertext, key, nonce)
    return plaintext.decode("utf-8")


def main() -> None:
    filepath = "secure_sample.dat"
    passphrase = "correct horse battery staple"
    data = "Confidential corporate document: Q3 strategy and financial projections."
    store_file(filepath, data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)


if __name__ == "__main__":
    main()