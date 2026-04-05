import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from passphrase and salt using PBKDF2."""
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        iterations=100_000,
        dklen=32
    )
    return key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """Encrypt data with the passphrase and write to filepath."""
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # File format: salt (16 bytes) || nonce (12 bytes) || ciphertext (includes GCM tag)
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read and decrypt file using the passphrase, returning the original data."""
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
    """Demonstrate storing and retrieving a secure document."""
    filepath = "secret_document.enc"
    passphrase = "my-super-secret-passphrase-2024!"
    
    sample_document = (
        "CONFIDENTIAL REPORT\n"
        "====================\n"
        "Project: Phoenix\n"
        "Status: Active\n"
        "Budget: $2,450,000\n"
        "Lead: Dr. Sarah Chen\n\n"
        "This document contains sensitive corporate information.\n"
        "Unauthorized access is strictly prohibited."
    )
    
    print("=== Secure Storage Demo ===\n")
    
    # Store the document
    print(f"Storing document to '{filepath}'...")
    store_file(filepath, sample_document, passphrase)
    print("Document stored successfully.\n")
    
    # Show that the file on disk is not readable
    with open(filepath, 'rb') as f:
        raw_content = f.read()
    print(f"Raw file size: {len(raw_content)} bytes")
    print(f"Raw file preview (hex): {raw_content[:48].hex()}...")
    print("(File contents are encrypted and unreadable without passphrase)\n")
    
    # Retrieve with correct passphrase
    print("Retrieving document with correct passphrase...")
    retrieved = retrieve_file(filepath, passphrase)
    print("Document retrieved successfully!\n")
    
    print("--- Retrieved Document ---")
    print(retrieved)
    print("--- End of Document ---\n")
    
    # Verify correctness
    if retrieved == sample_document:
        print("✓ Verification PASSED: Retrieved document matches original exactly.")
    else:
        print("✗ Verification FAILED: Retrieved document does not match original.")
    
    # Demonstrate that wrong passphrase fails
    print("\nAttempting retrieval with wrong passphrase...")
    try:
        retrieve_file(filepath, "wrong-passphrase")
        print("✗ ERROR: Decryption should have failed with wrong passphrase!")
    except Exception as e:
        print(f"✓ Correctly rejected wrong passphrase: {type(e).__name__}")
    
    # Clean up
    os.remove(filepath)
    print(f"\nCleaned up '{filepath}'.")


if __name__ == "__main__":
    main()