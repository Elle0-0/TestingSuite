import os
import hashlib
import hmac
from typing import Optional

_MAGIC = b"SSF1"
_SALT_SIZE = 16
_NONCE_SIZE = 16
_KEY_SIZE = 32
_PBKDF2_ITERS = 200_000
_BLOCK_SIZE = 32


def _keystream_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    return hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()


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


def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    master = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        _PBKDF2_ITERS,
        dklen=64,
    )
    return master[:32], master[32:]


def store_file(filepath: str, data: str, passphrase: str) -> None:
    plaintext = data.encode("utf-8")
    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    enc_key, mac_key = _derive_keys(passphrase, salt)
    ciphertext = _xor_stream(plaintext, enc_key, nonce)
    tag = hmac.new(mac_key, _MAGIC + salt + nonce + ciphertext, hashlib.sha256).digest()
    payload = _MAGIC + salt + nonce + ciphertext + tag
    with open(filepath, "wb") as f:
        f.write(payload)


def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        payload = f.read()

    min_len = len(_MAGIC) + _SALT_SIZE + _NONCE_SIZE + 32
    if len(payload) < min_len:
        raise ValueError("Invalid or corrupted file")

    magic = payload[:len(_MAGIC)]
    if magic != _MAGIC:
        raise ValueError("Invalid file format")

    idx = len(_MAGIC)
    salt = payload[idx:idx + _SALT_SIZE]
    idx += _SALT_SIZE
    nonce = payload[idx:idx + _NONCE_SIZE]
    idx += _NONCE_SIZE
    ciphertext = payload[idx:-32]
    tag = payload[-32:]

    enc_key, mac_key = _derive_keys(passphrase, salt)
    expected_tag = hmac.new(mac_key, _MAGIC + salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Incorrect passphrase or corrupted file")

    plaintext = _xor_stream(ciphertext, enc_key, nonce)
    return plaintext.decode("utf-8")


def main() -> None:
    filepath = "secure_sample.dat"
    data = "Confidential corporate document: Project Aurora budget and roadmap."
    passphrase = "correct horse battery staple"

    store_file(filepath, data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)


if __name__ == "__main__":
    main()