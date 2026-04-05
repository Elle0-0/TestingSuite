import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from the passphrase and salt using PBKDF2."""
    key = hashlib.pbkdf2_hmac(
        hash_name='sha256',
        password=passphrase.encode('utf-8'),
        salt=salt,
        iterations=200_000,
        dklen=32
    )
    return key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """Encrypt data with the passphrase and write it to filepath.

    File format: salt (16 bytes) || nonce (12 bytes) || ciphertext+tag
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(passphrase, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read the encrypted file and decrypt it with the passphrase."""
    with open(filepath, 'rb') as f:
        content = f.read()

    salt = content[:16]
    nonce = content[16:28]
    ciphertext = content[28:]

    key = _derive_key(passphrase, salt)

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext.decode('utf-8')


def main():
    filepath = "secure_document.enc"
    passphrase = "my-very-secret-passphrase-2024!"
    sample_document = (
        "CONFIDENTIAL REPORT\n"
        "====================\n"
        "Project Titan - Q4 Financial Summary\n"
        "Revenue: $12,450,000\n"
        "Net Profit: $3,200,000\n"
        "This document is classified and must not be shared outside the executive team.\n"
    )

    print("=== Secure Storage Demo ===\n")
    print("Original document:")
    print(sample_document)

    # Store the file
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and stored to '{filepath}'.\n")

    # Show that the raw file is not readable
    with open(filepath, 'rb') as f:
        raw = f.read()
    print(f"Raw file contents (first 80 bytes, hex): {raw[:80].hex()}\n")

    # Retrieve with correct passphrase
    retrieved = retrieve_file(filepath, passphrase)
    print("Retrieved document (correct passphrase):")
    print(retrieved)

    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("✓ Verification passed: retrieved document matches the original.\n")

    # Demonstrate that wrong passphrase fails
    try:
        retrieve_file(filepath, "wrong-passphrase")
        print("ERROR: Decryption with wrong passphrase should have failed!")
    except Exception as e:
        print(f"✓ Decryption with wrong passphrase correctly failed: {type(e).__name__}\n")

    # Clean up
    os.remove(filepath)
    print(f"Cleaned up '{filepath}'.")


if __name__ == "__main__":
    main()