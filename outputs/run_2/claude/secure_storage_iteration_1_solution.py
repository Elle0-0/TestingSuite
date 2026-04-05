import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from the passphrase using PBKDF2-HMAC-SHA256."""
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        iterations=200_000,
        dklen=32
    )
    return key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """Encrypt data with the passphrase and write to filepath.

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
    """Read and decrypt file contents using the passphrase.

    Returns the original plaintext string.
    Raises an exception if the passphrase is incorrect or the file is tampered with.
    """
    with open(filepath, 'rb') as f:
        file_data = f.read()

    salt = file_data[:16]
    nonce = file_data[16:28]
    ciphertext = file_data[28:]

    key = _derive_key(passphrase, salt)

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext.decode('utf-8')


def main():
    filepath = "confidential_document.enc"
    passphrase = "correct-horse-battery-staple"
    wrong_passphrase = "wrong-passphrase-attempt"

    sample_document = (
        "CONFIDENTIAL MEMO\n"
        "Date: 2024-01-15\n"
        "Subject: Project Phoenix - Q1 Strategy\n\n"
        "The projected revenue target for Q1 is $4.2M. "
        "Key partnerships with Acme Corp and Globex Industries "
        "are expected to close by end of February.\n\n"
        "This document is classified. Do not distribute."
    )

    # Store the document
    print("=== Secure Storage Demo ===\n")
    print("Storing confidential document...")
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and saved to '{filepath}'.\n")

    # Show that the raw file is not readable
    with open(filepath, 'rb') as f:
        raw = f.read()
    print(f"Raw file size: {len(raw)} bytes")
    print(f"Raw file preview (hex): {raw[:60].hex()}...\n")

    # Retrieve with correct passphrase
    print("Retrieving with correct passphrase...")
    retrieved = retrieve_file(filepath, passphrase)
    print(f"Retrieved document:\n{retrieved}\n")

    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("✓ Verification passed: retrieved data matches original.\n")

    # Attempt retrieval with wrong passphrase
    print("Attempting retrieval with wrong passphrase...")
    try:
        retrieve_file(filepath, wrong_passphrase)
        print("ERROR: Decryption should have failed with wrong passphrase!")
    except Exception as e:
        print(f"✓ Correctly rejected wrong passphrase: {type(e).__name__}\n")

    # Clean up
    os.remove(filepath)
    print("Demo complete. Temporary file removed.")


if __name__ == "__main__":
    main()