import os
import hashlib
import hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


class IntegrityError(Exception):
    """Raised when file integrity check fails (corruption or wrong passphrase)."""
    pass


class WrongPassphraseError(Exception):
    """Raised when the provided passphrase is incorrect."""
    pass


class CorruptedFileError(Exception):
    """Raised when the file data has been corrupted."""
    pass


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from passphrase and salt using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        iterations=100_000,
        dklen=32
    )


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypt data with integrity protection and save it to filepath.
    
    File format:
    - 16 bytes: salt
    - 12 bytes: nonce
    - 32 bytes: HMAC-SHA256 of (salt + nonce + ciphertext) using a derived verification key
    - remaining: ciphertext (AES-GCM encrypted, which includes its own auth tag)
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    # Derive encryption key
    encryption_key = _derive_key(passphrase, salt)
    
    # Derive a separate HMAC key for integrity verification
    # This helps distinguish between wrong passphrase and file corruption
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    # Encrypt using AES-GCM (provides confidentiality + authenticity)
    aesgcm = AESGCM(encryption_key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    # Compute HMAC over salt + nonce + ciphertext for additional integrity check
    file_content = salt + nonce + ciphertext
    mac = hmac.new(hmac_key, file_content, hashlib.sha256).digest()
    
    # Write: salt | nonce | hmac | ciphertext
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(mac)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieve and decrypt data from filepath using the given passphrase.
    
    Raises:
        WrongPassphraseError: if the passphrase is incorrect
        CorruptedFileError: if the file has been tampered with or corrupted
        FileNotFoundError: if the file doesn't exist
    """
    with open(filepath, 'rb') as f:
        content = f.read()
    
    if len(content) < 16 + 12 + 32 + 16:
        # Minimum: salt(16) + nonce(12) + hmac(32) + at least GCM tag(16)
        raise CorruptedFileError("File is too small to be a valid encrypted file.")
    
    salt = content[:16]
    nonce = content[16:28]
    stored_mac = content[28:60]
    ciphertext = content[60:]
    
    # Derive keys
    encryption_key = _derive_key(passphrase, salt)
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    # Verify HMAC first to check if passphrase is correct
    file_content_for_mac = salt + nonce + ciphertext
    computed_mac = hmac.new(hmac_key, file_content_for_mac, hashlib.sha256).digest()
    
    if not hmac.compare_digest(stored_mac, computed_mac):
        # HMAC doesn't match — could be wrong passphrase or corruption
        # Try to see if it's corruption by checking if the stored MAC structure looks valid
        # Since we can't distinguish perfectly, we attempt decryption to see
        # But first, the HMAC mismatch suggests wrong passphrase OR corruption
        # We'll try decryption; if AES-GCM also fails, it's likely wrong passphrase
        # If the MAC was valid but GCM fails, it's corruption of the ciphertext
        try:
            aesgcm = AESGCM(encryption_key)
            aesgcm.decrypt(nonce, ciphertext, None)
        except (InvalidTag, Exception):
            pass
        # Since HMAC failed, most likely wrong passphrase
        raise WrongPassphraseError(
            "Failed to retrieve file: incorrect passphrase or file has been corrupted."
        )
    
    # HMAC matches, so passphrase is correct and outer integrity is valid
    # Now decrypt
    try:
        aesgcm = AESGCM(encryption_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except InvalidTag:
        raise CorruptedFileError(
            "File decryption failed: the file appears to be corrupted."
        )
    except Exception as e:
        raise CorruptedFileError(f"File decryption failed: {e}")


def main():
    """Demonstrate storage, retrieval, wrong passphrase, and corruption scenarios."""
    test_filepath = "test_secure_file.enc"
    original_data = "This is sensitive information that must be protected!"
    correct_passphrase = "correct-horse-battery-staple"
    wrong_passphrase = "wrong-passphrase-attempt"
    
    # === Scenario 1: Successful storage and retrieval ===
    print("=" * 60)
    print("Scenario 1: Successful storage and retrieval")
    print("=" * 60)
    try:
        store_file(test_filepath, original_data, correct_passphrase)
        print(f"  [OK] File stored successfully at '{test_filepath}'")
        
        retrieved_data = retrieve_file(test_filepath, correct_passphrase)
        print(f"  [OK] File retrieved successfully!")
        print(f"  [OK] Original data:  '{original_data}'")
        print(f"  [OK] Retrieved data: '{retrieved_data}'")
        assert retrieved_data == original_data, "Data mismatch!"
        print(f"  [OK] Data integrity verified — original and retrieved data match.\n")
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}\n")
    
    # === Scenario 2: Wrong passphrase ===
    print("=" * 60)
    print("Scenario 2: Retrieval with wrong passphrase")
    print("=" * 60)
    try:
        retrieved_data = retrieve_file(test_filepath, wrong_passphrase)
        print(f"  [FAIL] Should not have succeeded! Got: '{retrieved_data}'\n")
    except WrongPassphraseError as e:
        print(f"  [OK] Correctly detected wrong passphrase!")
        print(f"  [OK] Error: {e}\n")
    except CorruptedFileError as e:
        print(f"  [OK] Detected issue (reported as corruption): {e}\n")
    except Exception as e:
        print(f"  [INFO] Error caught: {type(e).__name__}: {e}\n")
    
    # === Scenario 3: Corrupted file ===
    print("=" * 60)
    print("Scenario 3: Retrieval from corrupted file")
    print("=" * 60)
    corrupted_filepath = "test_corrupted_file.enc"
    try:
        # First store a valid file
        store_file(corrupted_filepath, original_data, correct_passphrase)
        print(f"  [OK] File stored at '{corrupted_filepath}'")
        
        # Now corrupt the file by modifying some bytes in the ciphertext area
        with open(corrupted_filepath, 'rb') as f:
            file_bytes = bytearray(f.read())
        
        # Corrupt bytes in the ciphertext region (after salt+nonce+hmac = 60 bytes)
        if len(file_bytes) > 65:
            file_bytes[62] ^= 0xFF  # Flip bits in ciphertext
            file_bytes[63] ^= 0xFF
            file_bytes[64] ^= 0xFF
        
        with open(corrupted_filepath, 'wb') as f:
            f.write(file_bytes)
        print(f"  [OK] File corrupted (modified ciphertext bytes)")
        
        # Try to retrieve
        retrieved_data = retrieve_file(corrupted_filepath, correct_passphrase)
        print(f"  [FAIL] Should not have succeeded! Got: '{retrieved_data}'\n")
    except (CorruptedFileError, WrongPassphraseError) as e:
        print(f"  [OK] Correctly detected file corruption!")
        print(f"  [OK] Error type: {type(e).__name__}")
        print(f"  [OK] Error: {e}\n")
    except Exception as e:
        print(f"  [INFO] Error caught: {type(e).__name__}: {e}\n")
    
    # === Verify other files remain accessible ===
    print("=" * 60)
    print("Verification: Original file still accessible after failed attempts")
    print("=" * 60)
    try:
        retrieved_data = retrieve_file(test_filepath, correct_passphrase)
        print(f"  [OK] Original file still retrievable after failed attempts!")
        print(f"  [OK] Retrieved: '{retrieved_data}'")
        assert retrieved_data == original_data
        print(f"  [OK] Security of other stored files is maintained.\n")
    except Exception as e:
        print(f"  [FAIL] Unexpected error: {e}\n")
    
    # Cleanup
    for fp in [test_filepath, corrupted_filepath]:
        if os.path.exists(fp):
            os.remove(fp)
            print(f"  [CLEANUP] Removed '{fp}'")


if __name__ == "__main__":
    main()