import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from passphrase and salt using PBKDF2-HMAC-SHA256."""
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
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # File format: salt (16 bytes) || nonce (12 bytes) || ciphertext (includes GCM tag)
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """Read encrypted file and decrypt with the passphrase, returning original data."""
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
    passphrase = "MyS3cur3P@ssphr@se!2024"
    
    sample_document = (
        "CONFIDENTIAL - Project Phoenix Status Report\n"
        "Date: 2024-01-15\n"
        "Classification: TOP SECRET\n\n"
        "Executive Summary:\n"
        "The new encryption module has passed all penetration testing phases. "
        "Deployment is scheduled for Q2 2024. Budget allocation: $2.4M.\n\n"
        "Key findings and sensitive financial data are enclosed.\n"
        "Do not distribute without authorization."
    )
    
    # Store the document securely
    print("Storing confidential document...")
    store_file(filepath, sample_document, passphrase)
    print(f"Document encrypted and saved to '{filepath}'.")
    
    # Show that the file on disk is not readable
    with open(filepath, 'rb') as f:
        raw_contents = f.read()
    print(f"\nRaw file size: {len(raw_contents)} bytes")
    print(f"Raw file preview (hex): {raw_contents[:64].hex()}...")
    print("(File contents are not human-readable without the passphrase)")
    
    # Retrieve with correct passphrase
    print("\nRetrieving document with correct passphrase...")
    retrieved = retrieve_file(filepath, passphrase)
    print("Decrypted document:")
    print("-" * 60)
    print(retrieved)
    print("-" * 60)
    
    # Verify correctness
    assert retrieved == sample_document, "ERROR: Retrieved data does not match original!"
    print("\n✓ Verification passed: retrieved document matches the original exactly.")
    
    # Demonstrate that wrong passphrase fails
    print("\nAttempting retrieval with wrong passphrase...")
    try:
        retrieve_file(filepath, "WrongPassphrase123")
        print("ERROR: Decryption should have failed with wrong passphrase!")
    except Exception as e:
        print(f"✓ Correctly rejected wrong passphrase: {type(e).__name__}")
    
    # Clean up
    os.remove(filepath)
    print(f"\nCleaned up '{filepath}'.")


if __name__ == "__main__":
    main()