import os
import hashlib

_SALT_SIZE = 16
_ITERATIONS = 200_000
_CHUNK_SIZE = 4096

def _derive_key(passphrase: str, salt: bytes, length: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, _ITERATIONS, dklen=length)

def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, key))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    plaintext = data.encode("utf-8")
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(passphrase, salt, len(plaintext))
    ciphertext = _xor_bytes(plaintext, key)
    with open(filepath, "wb") as f:
        f.write(salt + ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, "rb") as f:
        content = f.read()
    if len(content) < _SALT_SIZE:
        raise ValueError("Invalid encrypted file format")
    salt = content[:_SALT_SIZE]
    ciphertext = content[_SALT_SIZE:]
    key = _derive_key(passphrase, salt, len(ciphertext))
    plaintext = _xor_bytes(ciphertext, key)
    return plaintext.decode("utf-8")

def main() -> None:
    filepath = "sample.secure"
    data = "Confidential corporate document: Q4 strategy and financial projections."
    passphrase = "correct horse battery staple"
    store_file(filepath, data, passphrase)
    recovered = retrieve_file(filepath, passphrase)
    print(recovered)

if __name__ == "__main__":
    main()