import os
import hashlib
import base64

MAGIC = b"SECSTORE1"
SALT_SIZE = 16
NONCE_SIZE = 16
KEY_SIZE = 32
PBKDF2_ITERATIONS = 200_000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=KEY_SIZE)

def _keystream_block(key: bytes, nonce: bytes, counter: int) -> bytes:
    return hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()

def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    i = 0
    while i < len(data):
        block = _keystream_block(key, nonce, counter)
        chunk = data[i:i + len(block)]
        out.extend(b ^ k for b, k in zip(chunk, block))
        i += len(block)
        counter += 1
    return bytes(out)

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    plaintext = data.encode("utf-8")
    ciphertext = _xor_stream(plaintext, key, nonce)
    check = hashlib.sha256(key + b"verify").digest()[:16]
    payload = MAGIC + salt + nonce + check + ciphertext
    with open(filepath, "wb") as f:
        f.write(base64.b64encode(payload))

def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        raw = base64.b64decode(f.read())
    if len(raw) < len(MAGIC) + SALT_SIZE + NONCE_SIZE + 16 or raw[:len(MAGIC)] != MAGIC:
        raise ValueError("Invalid file format")
    pos = len(MAGIC)
    salt = raw[pos:pos + SALT_SIZE]
    pos += SALT_SIZE
    nonce = raw[pos:pos + NONCE_SIZE]
    pos += NONCE_SIZE
    stored_check = raw[pos:pos + 16]
    pos += 16
    ciphertext = raw[pos:]
    key = _derive_key(passphrase, salt)
    check = hashlib.sha256(key + b"verify").digest()[:16]
    if check != stored_check:
        raise ValueError("Incorrect passphrase")
    plaintext = _xor_stream(ciphertext, key, nonce)
    return plaintext.decode("utf-8")

def main() -> None:
    filepath = "secure_document.dat"
    data = "Confidential corporate document: Q4 acquisition strategy."
    passphrase = "correct horse battery staple"
    store_file(filepath, data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)

if __name__ == "__main__":
    main()