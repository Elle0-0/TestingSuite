import os
import base64
import hashlib
import hmac

MAGIC = b"SECSTORE1"
SALT_SIZE = 16
NONCE_SIZE = 16
KEY_SIZE = 32
PBKDF2_ITERS = 200_000


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
    master = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERS, dklen=64)
    return master[:32], master[32:]


def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    enc_key, mac_key = _derive_keys(passphrase, salt)
    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream(plaintext, enc_key, nonce)
    tag = hmac.new(mac_key, MAGIC + salt + nonce + ciphertext, hashlib.sha256).digest()
    blob = MAGIC + salt + nonce + tag + ciphertext
    with open(filepath, "wb") as f:
        f.write(base64.b64encode(blob))


def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        encoded = f.read()
    blob = base64.b64decode(encoded)

    min_len = len(MAGIC) + SALT_SIZE + NONCE_SIZE + 32
    if len(blob) < min_len or blob[:len(MAGIC)] != MAGIC:
        raise ValueError("Invalid file format")

    idx = len(MAGIC)
    salt = blob[idx:idx + SALT_SIZE]
    idx += SALT_SIZE
    nonce = blob[idx:idx + NONCE_SIZE]
    idx += NONCE_SIZE
    tag = blob[idx:idx + 32]
    idx += 32
    ciphertext = blob[idx:]

    enc_key, mac_key = _derive_keys(passphrase, salt)
    expected_tag = hmac.new(mac_key, MAGIC + salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Incorrect passphrase or tampered file")

    plaintext = _xor_stream(ciphertext, enc_key, nonce)
    return plaintext.decode("utf-8")


def main() -> None:
    path = "sample_secure_document.dat"
    sample_data = "Confidential corporate document: Q4 security roadmap."
    passphrase = "correct horse battery staple"

    store_file(path, sample_data, passphrase)
    recovered = retrieve_file(path, passphrase)
    print(recovered)


if __name__ == "__main__":
    main()