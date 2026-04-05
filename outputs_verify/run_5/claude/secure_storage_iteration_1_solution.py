import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a passphrase and salt using PBKDF2."""
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
    
    # File format: salt (16 bytes) + nonce (12 bytes) + ciphertext (variable)
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read and decrypt file using the passphrase, returning the original data."""
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
    """Demonstrate storing and retrieving a confidential document."""
    filepath = "confidential_document.enc"
    passphrase = "my-s3cur3-p@ssphr@se!"
    
    sample_document = (
        "CONFIDENTIAL REPORT\n"
        "====================\n"
        "Project: Phoenix\n"
        "Classification: Top Secret\n\n"
        "The quarterly revenue exceeded projections by 15%. "
        "Key acquisitions are proceeding as planned. "
        "Board approval is expected by end of Q3.\n\n"
        "— Chief Strategy Officer"
    )
    
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
    print(f"Raw file size: {len(raw)} bytes")
    print(f"Raw file content (first 80 bytes hex): {raw[:80].hex()}")
    print()
    
    # Retrieve with correct passphrase
    retrieved = retrieve_file(filepath, passphrase)
    print("Retrieved document (correct passphrase):")
    print(retrieved)
    print()
    
    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("✓ Verification passed: retrieved document matches the original exactly.")
    print()
    
    # Demonstrate that wrong passphrase fails
    wrong_passphrase = "wrong-passphrase"
    try:
        retrieve_file(filepath, wrong_passphrase)
        print("✗ ERROR: Decryption with wrong passphrase should have failed!")
    except Exception as e:
        print(f"✓ Decryption with wrong passphrase correctly failed: {type(e).__name__}")
    
    # Clean up
    os.remove(filepath)
    print(f"\nCleaned up '{filepath}'.")


if __name__ == "__main__":
    main()