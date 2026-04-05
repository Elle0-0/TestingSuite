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
    """Encrypt data with the passphrase and write to filepath."""
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # File format: salt (16 bytes) || nonce (12 bytes) || ciphertext (variable)
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read and decrypt the file using the passphrase, returning the original data."""
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
    sample_document = (
        "CONFIDENTIAL REPORT\n"
        "Project Falcon - Q4 Financial Summary\n"
        "Revenue: $12,450,000\n"
        "Net Profit: $3,200,000\n"
        "This document is classified and must not be disclosed."
    )
    passphrase = "correct-horse-battery-staple"
    filepath = "secure_document.enc"
    
    print("=== Secure Storage Demo ===\n")
    print("Original document:")
    print(sample_document)
    print()
    
    # Store the file
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and stored to '{filepath}'.")
    
    # Show that the raw file is not readable
    with open(filepath, 'rb') as f:
        raw = f.read()
    print(f"\nRaw file contents (first 80 bytes): {raw[:80]}")
    print("(Not human-readable — data is encrypted)\n")
    
    # Retrieve with correct passphrase
    retrieved = retrieve_file(filepath, passphrase)
    print("Retrieved document (correct passphrase):")
    print(retrieved)
    print()
    
    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("✓ Verification passed: retrieved document matches the original.\n")
    
    # Demonstrate that wrong passphrase fails
    wrong_passphrase = "wrong-passphrase"
    try:
        retrieve_file(filepath, wrong_passphrase)
        print("✗ ERROR: Decryption should have failed with wrong passphrase!")
    except Exception as e:
        print(f"✓ Correct behavior: wrong passphrase rejected ({type(e).__name__})")
    
    # Clean up
    os.remove(filepath)
    print(f"\nCleaned up '{filepath}'.")


if __name__ == "__main__":
    main()