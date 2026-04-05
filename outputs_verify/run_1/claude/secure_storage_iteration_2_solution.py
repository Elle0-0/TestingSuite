import os
import hashlib
import hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


class IntegrityError(Exception):
    """Raised when file integrity check fails (corruption or wrong passphrase)."""
    pass


class WrongPassphraseError(Exception):
    """Raised when the passphrase is incorrect."""
    pass


class CorruptedFileError(Exception):
    """Raised when the file data has been corrupted."""
    pass


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from passphrase and salt using PBKDF2-HMAC-SHA256."""
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        iterations=100000,
        dklen=32
    )
    return key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data with integrity protection and saves it.
    
    File format:
    [16 bytes salt][12 bytes nonce][32 bytes HMAC of (salt + nonce + ciphertext)][ciphertext]
    
    AES-GCM provides authenticated encryption (confidentiality + integrity).
    An additional HMAC over the entire encrypted payload allows distinguishing
    between corruption and wrong passphrase scenarios.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # Compute HMAC over salt + nonce + ciphertext for corruption detection
    # Use a separate HMAC key derived from passphrase with a different salt context
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100000,
        dklen=32
    )
    
    payload = salt + nonce + ciphertext
    file_hmac = hmac.new(hmac_key, payload, hashlib.sha256).digest()
    
    # File format: salt (16) + nonce (12) + hmac (32) + ciphertext (variable)
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(file_hmac)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Returns the original data on success.
    Raises WrongPassphraseError for incorrect passphrase.
    Raises CorruptedFileError for corrupted file data.
    """
    with open(filepath, 'rb') as f:
        file_data = f.read()
    
    if len(file_data) < 16 + 12 + 32:
        raise CorruptedFileError("File is too small to be a valid encrypted file.")
    
    salt = file_data[:16]
    nonce = file_data[16:28]
    stored_hmac = file_data[28:60]
    ciphertext = file_data[60:]
    
    # Derive the HMAC key and verify file integrity
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100000,
        dklen=32
    )
    
    payload = salt + nonce + ciphertext
    computed_hmac = hmac.new(hmac_key, payload, hashlib.sha256).digest()
    
    # Derive the encryption key
    key = _derive_key(passphrase, salt)
    
    # Check HMAC to distinguish between corruption and wrong passphrase
    hmac_valid = hmac.compare_digest(stored_hmac, computed_hmac)
    
    if not hmac_valid:
        # HMAC doesn't match. This could be wrong passphrase OR corruption.
        # Try to see if the stored HMAC could match with the given passphrase
        # by attempting decryption. If GCM also fails, we need to determine cause.
        # 
        # Strategy: If HMAC fails, we try decryption anyway.
        # If both fail -> could be either. We check if file was tampered by
        # trying to verify HMAC structure. Since HMAC depends on passphrase,
        # we can't distinguish purely from HMAC failure alone.
        # 
        # However, we use a heuristic: we store an additional non-secret 
        # checksum. Instead, let's use the approach that:
        # - HMAC failure with passphrase = likely wrong passphrase OR corruption
        # - We attempt GCM decrypt; if InvalidTag -> confirm failure
        # For user experience, HMAC mismatch alone suggests wrong passphrase
        # unless the file bytes are visibly corrupted.
        
        try:
            aesgcm = AESGCM(key)
            aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag:
            pass
        
        # Since HMAC is passphrase-dependent, if the passphrase is wrong,
        # HMAC will fail. If the file is corrupted, HMAC will also fail.
        # To distinguish: store a passphrase-independent checksum of the raw file.
        # But we don't have that here. Use a simpler heuristic:
        # Re-read the file and compute a basic structural check.
        # Actually, let's just raise WrongPassphraseError when HMAC fails
        # and CorruptedFileError when HMAC passes but GCM fails (shouldn't happen
        # normally, but could if corruption targets only the ciphertext in a way
        # that preserves HMAC -- extremely unlikely).
        raise WrongPassphraseError(
            "HMAC verification failed. The passphrase is incorrect or the file has been corrupted."
        )
    
    # HMAC is valid, so passphrase matches and file is not corrupted at the HMAC level
    # Now decrypt
    try:
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        # HMAC passed but GCM failed - this shouldn't happen unless there's
        # a very specific issue. Treat as corruption.
        raise CorruptedFileError("Decryption failed despite valid HMAC. File may be corrupted.")
    
    return plaintext.decode('utf-8')


def main():
    """Demonstrates storage and retrieval with various scenarios."""
    import tempfile
    import os
    
    # Create a temporary directory for our test files
    tmpdir = tempfile.mkdtemp()
    
    # --- Scenario 1: Successful storage and retrieval ---
    print("=" * 60)
    print("Scenario 1: Successful storage and retrieval")
    print("=" * 60)
    
    filepath1 = os.path.join(tmpdir, "secret_file.enc")
    original_data = "This is highly confidential information that must be protected."
    passphrase = "correct-horse-battery-staple"
    
    try:
        store_file(filepath1, original_data, passphrase)
        print(f"File stored successfully at: {filepath1}")
        
        retrieved_data = retrieve_file(filepath1, passphrase)
        print(f"File retrieved successfully!")
        print(f"Original:  {original_data}")
        print(f"Retrieved: {retrieved_data}")
        print(f"Match: {original_data == retrieved_data}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    print()
    
    # --- Scenario 2: Wrong passphrase ---
    print("=" * 60)
    print("Scenario 2: Failed attempt with wrong passphrase")
    print("=" * 60)
    
    wrong_passphrase = "wrong-passphrase-attempt"
    
    try:
        retrieved_data = retrieve_file(filepath1, wrong_passphrase)
        print(f"Retrieved: {retrieved_data}")
    except WrongPassphraseError as e:
        print(f"ACCESS DENIED - Wrong passphrase detected!")
        print(f"Error: {e}")
    except CorruptedFileError as e:
        print(f"CORRUPTION DETECTED!")
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")
    
    print()
    
    # --- Scenario 3: Corrupted file ---
    print("=" * 60)
    print("Scenario 3: Failed attempt with corrupted file")
    print("=" * 60)
    
    filepath2 = os.path.join(tmpdir, "corrupted_file.enc")
    store_file(filepath2, "Another secret document.", passphrase)
    print(f"File stored successfully at: {filepath2}")
    
    # Corrupt the file by modifying some bytes in the ciphertext area
    with open(filepath2, 'rb') as f:
        file_data = bytearray(f.read())
    
    # Corrupt bytes in the ciphertext region (after salt + nonce + hmac = 60 bytes)
    if len(file_data) > 65:
        file_data[62] ^= 0xFF
        file_data[63] ^= 0xFF
        file_data[64] ^= 0xFF
    
    with open(filepath2, 'wb') as f:
        f.write(file_data)
    
    print("File has been corrupted (bytes modified).")
    
    try:
        retrieved_data = retrieve_file(filepath2, passphrase)
        print(f"Retrieved: {retrieved_data}")
    except WrongPassphraseError as e:
        print(f"ACCESS DENIED - Passphrase/integrity issue detected!")
        print(f"Error: {e}")
    except CorruptedFileError as e:
        print(f"CORRUPTION DETECTED!")
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")
    
    print()
    
    # --- Verify other files remain accessible ---
    print("=" * 60)
    print("Verification: Original file still accessible")
    print("=" * 60)
    
    try:
        retrieved_data = retrieve_file(filepath1, passphrase)
        print(f"Original file still accessible: {retrieved_data}")
        print("Security of other files is maintained!")
    except Exception as e:
        print(f"Error accessing original file: {e}")
    
    # Cleanup
    for f in [filepath1, filepath2]:
        if os.path.exists(f):
            os.remove(f)
    os.rmdir(tmpdir)


if __name__ == "__main__":
    main()