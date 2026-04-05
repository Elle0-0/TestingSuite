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
        f.write(salt + nonce + ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read an encrypted file and decrypt it with the passphrase.
    
    Returns the original plaintext string.
    Raises an exception if the passphrase is incorrect or the file is tampered with.
    """
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
        "CONFIDENTIAL MEMO\n"
        "Project Codename: Phoenix\n"
        "Budget: $4,200,000\n"
        "Timeline: Q3 2025 - Q1 2026\n"
        "This document contains proprietary information. "
        "Unauthorized disclosure is strictly prohibited."
    )
    
    passphrase = "correct-horse-battery-staple"
    filepath = "secure_document.enc"
    
    # Store the document
    print("Storing confidential document...")
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and saved to '{filepath}'.")
    
    # Verify the file on disk is not readable as plaintext
    with open(filepath, 'rb') as f:
        raw_contents = f.read()
    print(f"\nRaw file size: {len(raw_contents)} bytes")
    print(f"Raw file is plaintext readable: {'Phoenix' in raw_contents.decode('latin-1')}")
    
    # Retrieve with correct passphrase
    print("\nRetrieving document with correct passphrase...")
    retrieved = retrieve_file(filepath, passphrase)
    print(f"Retrieved document:\n{retrieved}")
    
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