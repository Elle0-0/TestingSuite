import os
import hashlib
import secrets

_SALT_SIZE = 16
_NONCE_SIZE = 16
_KEY_SIZE = 32
_ITERATIONS = 200_000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, _ITERATIONS, dklen=_KEY_SIZE)

def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])

def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))

def _mac(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return hashlib.sha256(key + nonce + ciphertext).digest()

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = secrets.token_bytes(_SALT_SIZE)
    nonce = secrets.token_bytes(_NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    plaintext = data.encode("utf-8")
    ciphertext = _xor_bytes(plaintext, _keystream(key, nonce, len(plaintext)))
    tag = _mac(key, nonce, ciphertext)
    with open(filepath, "wb") as f:
        f.write(b"SS1")
        f.write(salt)
        f.write(nonce)
        f.write(tag)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        blob = f.read()
    header_len = 3 + _SALT_SIZE + _NONCE_SIZE + 32
    if len(blob) < header_len or blob[:3] != b"SS1":
        raise ValueError("Invalid file format")
    salt = blob[3:3 + _SALT_SIZE]
    nonce_start = 3 + _SALT_SIZE
    nonce = blob[nonce_start:nonce_start + _NONCE_SIZE]
    tag_start = nonce_start + _NONCE_SIZE
    tag = blob[tag_start:tag_start + 32]
    ciphertext = blob[tag_start + 32:]
    key = _derive_key(passphrase, salt)
    expected_tag = _mac(key, nonce, ciphertext)
    if not secrets.compare_digest(tag, expected_tag):
        raise ValueError("Incorrect passphrase or corrupted file")
    plaintext = _xor_bytes(ciphertext, _keystream(key, nonce, len(ciphertext)))
    return plaintext.decode("utf-8")

def main() -> None:
    filepath = "secure_sample.dat"
    passphrase = "correct horse battery staple"
    sample_data = "Confidential corporate document: Q4 security roadmap."
    store_file(filepath, sample_data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)

if __name__ == "__main__":
    main()