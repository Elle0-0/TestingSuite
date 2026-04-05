import os
import base64
import hashlib
import hmac

_SALT_SIZE = 16
_NONCE_SIZE = 16
_KEY_SIZE = 32
_PBKDF2_ITERATIONS = 200_000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
        dklen=_KEY_SIZE,
    )

def _keystream_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    counter_bytes = counter.to_bytes(8, "big")
    return hashlib.sha256(key + nonce + counter_bytes).digest()

def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray(len(data))
    counter = 0
    i = 0
    while i < len(data):
        block = _keystream_block(key, nonce, counter)
        chunk = data[i:i + len(block)]
        for j, b in enumerate(chunk):
            out[i + j] = b ^ block[j]
        i += len(block)
        counter += 1
    return bytes(out)

def _mac(key: bytes, salt: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return hmac.new(key, salt + nonce + ciphertext, hashlib.sha256).digest()

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream(plaintext, key, nonce)
    tag = _mac(key, salt, nonce, ciphertext)
    payload = b"CSF1" + salt + nonce + tag + ciphertext
    with open(filepath, "wb") as f:
        f.write(base64.b64encode(payload))

def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        raw = base64.b64decode(f.read())

    if len(raw) < 4 + _SALT_SIZE + _NONCE_SIZE + 32:
        raise ValueError("Invalid encrypted file format")

    magic = raw[:4]
    if magic != b"CSF1":
        raise ValueError("Unrecognized file format")

    offset = 4
    salt = raw[offset:offset + _SALT_SIZE]
    offset += _SALT_SIZE
    nonce = raw[offset:offset + _NONCE_SIZE]
    offset += _NONCE_SIZE
    tag = raw[offset:offset + 32]
    offset += 32
    ciphertext = raw[offset:]

    key = _derive_key(passphrase, salt)
    expected_tag = _mac(key, salt, nonce, ciphertext)
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Incorrect passphrase or corrupted file")

    plaintext = _xor_stream(ciphertext, key, nonce)
    return plaintext.decode("utf-8")

def main() -> None:
    filepath = "secure_sample.dat"
    sample_data = "Confidential corporate document: Q3 acquisition strategy."
    passphrase = "correct horse battery staple"

    store_file(filepath, sample_data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)

if __name__ == "__main__":
    main()