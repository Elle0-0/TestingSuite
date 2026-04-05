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
    """Encrypt data with the passphrase and save to filepath."""
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # File format: salt (16 bytes) + nonce (12 bytes) + ciphertext (includes GCM tag)
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read and decrypt file using the passphrase, returning original data."""
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
        "Project: Phoenix\n"
        "Status: Active\n"
        "Budget: $2,450,000\n"
        "This document contains sensitive corporate information "
        "that must be protected at all times."
    )
    
    filepath = "secure_document.enc"
    passphrase = "correct-horse-battery-staple"
    
    print("=== Secure Storage Demo ===\n")
    print(f"Original document:\n{sample_document}\n")
    
    # Store the file
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and stored to '{filepath}'.")
    
    # Show that the raw file is not readable
    with open(filepath, 'rb') as f:
        raw = f.read()
    print(f"Raw file size: {len(raw)} bytes")
    print(f"Raw file (hex preview): {raw[:64].hex()}...\n")
    
    # Retrieve with correct passphrase
    retrieved = retrieve_file(filepath, passphrase)
    print(f"Retrieved document:\n{retrieved}\n")
    
    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("✓ Verification passed: retrieved document matches the original.\n")
    
    # Demonstrate that wrong passphrase fails
    wrong_passphrase = "wrong-passphrase"
    try:
        retrieve_file(filepath, wrong_passphrase)
        print("ERROR: Decryption should have failed with wrong passphrase!")
    except Exception as e:
        print(f"✓ Correctly rejected wrong passphrase: {type(e).__name__}")
    
    # Clean up
    os.remove(filepath)
    print(f"\nCleaned up '{filepath}'.")


if __name__ == "__main__":
    main()