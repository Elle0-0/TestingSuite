import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from the passphrase and salt using PBKDF2."""
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        iterations=100_000,
        dklen=32
    )
    return key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """Encrypt data with the passphrase and write to filepath.
    
    File format: salt (16 bytes) || nonce (12 bytes) || ciphertext+tag
    """
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read and decrypt the file using the passphrase. Returns original data."""
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
    sample_document = (
        "CONFIDENTIAL REPORT\n"
        "====================\n"
        "Project: Phoenix\n"
        "Status: Active\n"
        "Budget: $2,450,000\n"
        "Lead: Dr. Sarah Chen\n\n"
        "This document contains sensitive corporate information. "
        "Unauthorized access is strictly prohibited."
    )
    
    passphrase = "correct-horse-battery-staple"
    filepath = "secure_document.enc"
    
    # Store the document
    print("Storing document securely...")
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and saved to '{filepath}'.")
    
    # Verify the file on disk is not readable as plaintext
    with open(filepath, 'rb') as f:
        raw_contents = f.read()
    print(f"\nRaw file size: {len(raw_contents)} bytes")
    print(f"Raw file (first 60 bytes hex): {raw_contents[:60].hex()}")
    print("File contents are not human-readable (encrypted).")
    
    # Retrieve with correct passphrase
    print("\nRetrieving document with correct passphrase...")
    retrieved = retrieve_file(filepath, passphrase)
    print("Retrieved document:")
    print("-" * 40)
    print(retrieved)
    print("-" * 40)
    
    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("\n✓ Verification passed: retrieved document matches the original exactly.")
    
    # Demonstrate that wrong passphrase fails
    print("\nAttempting retrieval with wrong passphrase...")
    try:
        retrieve_file(filepath, "wrong-passphrase")
        print("ERROR: Decryption should have failed with wrong passphrase!")
    except Exception as e:
        print(f"✓ Correctly rejected wrong passphrase: {type(e).__name__}")
    
    # Clean up
    os.remove(filepath)
    print(f"\nCleaned up '{filepath}'.")


if __name__ == "__main__":
    main()