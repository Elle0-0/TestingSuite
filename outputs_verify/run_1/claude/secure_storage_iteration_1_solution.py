import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from the passphrase using PBKDF2-HMAC-SHA256."""
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
    nonce = os.urandom(12)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    with open(filepath, 'wb') as f:
        f.write(salt + nonce + ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read and decrypt the file using the passphrase, returning the original string."""
    with open(filepath, 'rb') as f:
        raw = f.read()
    
    salt = raw[:16]
    nonce = raw[16:28]
    ciphertext = raw[28:]
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    
    return plaintext.decode('utf-8')


def main():
    sample_document = (
        "CONFIDENTIAL REPORT\n"
        "====================\n"
        "Project Titan - Q4 Financial Summary\n"
        "Revenue: $14.2M | Expenses: $9.8M | Net: $4.4M\n"
        "Status: On track for annual targets.\n"
        "This document is classified and must not be shared externally."
    )
    
    passphrase = "correct-horse-battery-staple"
    filepath = "secure_document.enc"
    
    # Store the document
    print("Storing document securely...")
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and saved to '{filepath}'.")
    
    # Show that the raw file is not human-readable
    with open(filepath, 'rb') as f:
        raw_bytes = f.read()
    print(f"\nRaw file contents (first 80 bytes, hex): {raw_bytes[:80].hex()}")
    print("(File is not readable without the correct passphrase.)")
    
    # Retrieve with the correct passphrase
    print("\nRetrieving document with correct passphrase...")
    retrieved = retrieve_file(filepath, passphrase)
    print("Retrieved document:")
    print(retrieved)
    
    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("\n✓ Verification passed: retrieved document matches the original exactly.")
    
    # Demonstrate that wrong passphrase fails
    print("\nAttempting retrieval with wrong passphrase...")
    try:
        retrieve_file(filepath, "wrong-passphrase")
        print("ERROR: Decryption should have failed!")
    except Exception as e:
        print(f"✓ Correctly denied access: {type(e).__name__}")
    
    # Clean up
    os.remove(filepath)
    print(f"\nCleaned up '{filepath}'.")


if __name__ == "__main__":
    main()