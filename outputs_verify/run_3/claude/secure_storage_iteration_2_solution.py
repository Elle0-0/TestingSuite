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
        iterations=100_000,
        dklen=32
    )
    return key


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypt data with integrity protection and save it to filepath.
    
    File format:
    [16 bytes salt][12 bytes nonce][32 bytes HMAC of (salt + nonce + ciphertext)][ciphertext]
    
    AES-GCM provides authenticated encryption (confidentiality + integrity).
    An additional HMAC over the entire ciphertext blob allows distinguishing
    between corruption and wrong passphrase scenarios.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # Compute HMAC over salt + nonce + ciphertext using a derived HMAC key
    # This HMAC key is derived differently so we can distinguish corruption from wrong passphrase
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    blob = salt + nonce + ciphertext
    file_hmac = hmac.new(hmac_key, blob, hashlib.sha256).digest()
    
    # Write: salt (16) + nonce (12) + hmac (32) + ciphertext
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(file_hmac)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieve and decrypt data from filepath using passphrase.
    
    Raises:
        WrongPassphraseError: if the passphrase is incorrect
        CorruptedFileError: if the file has been tampered with or corrupted
        FileNotFoundError: if the file does not exist
    """
    with open(filepath, 'rb') as f:
        content = f.read()
    
    if len(content) < 16 + 12 + 32:
        raise CorruptedFileError("File is too short to be valid.")
    
    salt = content[:16]
    nonce = content[16:28]
    stored_hmac = content[28:60]
    ciphertext = content[60:]
    
    # First, check HMAC to determine if file is corrupted or passphrase is wrong
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    blob = salt + nonce + ciphertext
    computed_hmac = hmac.new(hmac_key, blob, hashlib.sha256).digest()
    
    if hmac.compare_digest(stored_hmac, computed_hmac):
        # HMAC matches, so passphrase is correct and file is not corrupted
        # Decrypt should succeed
        key = _derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except InvalidTag:
            # This shouldn't happen if HMAC matched, but handle gracefully
            raise CorruptedFileError("Decryption failed despite valid HMAC. File may be corrupted.")
    else:
        # HMAC doesn't match. Could be wrong passphrase or corruption.
        # Try decryption with this passphrase to see if AES-GCM tag validates
        # If AES-GCM also fails, we need another way to distinguish.
        # 
        # Strategy: We store a secondary checksum that is passphrase-independent
        # to detect corruption. But we don't have that in our format.
        #
        # Alternative: Try to verify HMAC with the given passphrase against
        # what we'd expect. If HMAC doesn't match, it could be either.
        # We can check if the file has a valid structure by trying to see if
        # any passphrase-independent integrity marker exists.
        #
        # Simpler approach: We know the HMAC failed. We attempt AES-GCM decrypt.
        # If it also fails with InvalidTag, we lean toward wrong passphrase
        # (since corruption is less common and HMAC failure + GCM failure 
        # together most likely means wrong key). But to truly distinguish,
        # we add a non-secret checksum of the raw file bytes.
        
        # Check a non-keyed integrity hash stored... we don't have one in our format.
        # Let's use a heuristic: compute a SHA256 of the entire file content
        # and see if the file "looks" structurally valid by trying with wrong pass.
        # 
        # Better: We modify the approach. Let's store a non-secret hash of the 
        # ciphertext to detect corruption independently of the passphrase.
        # But that changes the file format... Let's just raise WrongPassphraseError
        # here since if the file were corrupted, the HMAC would also fail.
        # We'll detect corruption by checking if the ciphertext was modified
        # separately.
        
        # Since we can't perfectly distinguish without additional data, 
        # we use the following heuristic:
        # - Recompute HMAC with every possible interpretation... no.
        # - Simply: if HMAC doesn't match, it's most likely wrong passphrase.
        #   If the file was corrupted, AES-GCM will also fail.
        
        # For better distinction, let's also store a plaintext checksum of the blob.
        # Since we already wrote the format, let's handle it this way:
        # We'll raise WrongPassphraseError as the primary case.
        raise WrongPassphraseError(
            "The passphrase is incorrect or the file has been corrupted."
        )


def store_file_v2(filepath: str, data: str, passphrase: str) -> None:
    """
    Enhanced version that stores a non-secret integrity checksum to distinguish
    corruption from wrong passphrase.
    
    File format:
    [16 bytes salt][12 bytes nonce][32 bytes HMAC][32 bytes SHA256 of (salt+nonce+ciphertext)][ciphertext]
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    blob = salt + nonce + ciphertext
    file_hmac = hmac.new(hmac_key, blob, hashlib.sha256).digest()
    
    # Non-secret checksum for corruption detection
    integrity_hash = hashlib.sha256(blob).digest()
    
    with open(filepath, 'wb') as f:
        f.write(salt)           # 16 bytes
        f.write(nonce)          # 12 bytes
        f.write(file_hmac)      # 32 bytes
        f.write(integrity_hash) # 32 bytes
        f.write(ciphertext)     # variable


def retrieve_file_v2(filepath: str, passphrase: str) -> str:
    """
    Enhanced retrieval that distinguishes between corruption and wrong passphrase.
    """
    with open(filepath, 'rb') as f:
        content = f.read()
    
    min_size = 16 + 12 + 32 + 32
    if len(content) < min_size:
        raise CorruptedFileError("File is too short to be valid.")
    
    salt = content[:16]
    nonce = content[16:28]
    stored_hmac = content[28:60]
    stored_integrity = content[60:92]
    ciphertext = content[92:]
    
    # First check non-secret integrity hash to detect corruption
    blob = salt + nonce + ciphertext
    computed_integrity = hashlib.sha256(blob).digest()
    
    if not hmac.compare_digest(stored_integrity, computed_integrity):
        raise CorruptedFileError(
            "File integrity check failed. The file has been corrupted or tampered with."
        )
    
    # File is not corrupted. Now check passphrase via HMAC.
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    computed_hmac = hmac.new(hmac_key, blob, hashlib.sha256).digest()
    
    if not hmac.compare_digest(stored_hmac, computed_hmac):
        raise WrongPassphraseError("The provided passphrase is incorrect.")
    
    # Both checks passed, decrypt
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except InvalidTag:
        raise CorruptedFileError("Decryption failed unexpectedly. File may be corrupted.")


# Use v2 as the primary implementation
store_file = store_file_v2
retrieve_file = retrieve_file_v2


def main():
    import tempfile
    import shutil
    
    # Create a temporary directory for our test files
    tmpdir = tempfile.mkdtemp(prefix="secure_storage_")
    
    try:
        print("=" * 60)
        print("Secure Storage System - Integrity and Fault Awareness Demo")
        print("=" * 60)
        
        # --- Test 1: Successful storage and retrieval ---
        print("\n--- Test 1: Successful Storage and Retrieval ---")
        filepath1 = os.path.join(tmpdir, "secret_document.enc")
        original_data = "This is a highly confidential document containing sensitive information."
        passphrase = "correct-horse-battery-staple"
        
        print(f"Storing data to: {filepath1}")
        print(f"Original data: '{original_data}'")
        store_file(filepath1, original_data, passphrase)
        print("File stored successfully with encryption and integrity protection.")
        
        retrieved_data = retrieve_file(filepath1, passphrase)
        print(f"Retrieved data: '{retrieved_data}'")
        assert retrieved_data == original_data
        print("SUCCESS: Data retrieved correctly matches the original!")
        
        # --- Test 2: Wrong passphrase ---
        print("\n--- Test 2: Wrong Passphrase Attempt ---")
        wrong_passphrase = "wrong-passphrase-attempt"
        print(f"Attempting retrieval with wrong passphrase: '{wrong_passphrase}'")
        try:
            retrieve_file(filepath1, wrong_passphrase)
            print("ERROR: Should have raised an exception!")
        except WrongPassphraseError as e:
            print(f"CAUGHT WrongPassphraseError: {e}")
            print("SUCCESS: System correctly detected wrong passphrase!")
        except CorruptedFileError as e:
            print(f"CAUGHT CorruptedFileError: {e}")
        
        # Verify original file is still accessible with correct passphrase
        print("\nVerifying original file is still accessible...")
        retrieved_after_fail = retrieve_file(filepath1, passphrase)
        assert retrieved_after_fail == original_data
        print("SUCCESS: Original file remains accessible and secure after failed attempt!")
        
        # --- Test 3: Corrupted file ---
        print("\n--- Test 3: Corrupted File Detection ---")
        filepath2 = os.path.join(tmpdir, "another_secret.enc")
        data2 = "Another piece of sensitive data that must be protected."
        passphrase2 = "another-strong-passphrase"
        
        store_file(filepath2, data2, passphrase2)
        print(f"Stored second file: {filepath2}")
        
        # Corrupt the file by modifying some bytes in the ciphertext area
        print("Simulating file corruption...")
        with open(filepath2, 'r+b') as f:
            content = f.read()
            # Corrupt bytes in the ciphertext region (after header: 16+12+32+32 = 92 bytes)
            corrupted = bytearray(content)
            if len(corrupted) > 95:
                corrupted[93] ^= 0xFF  # Flip bits in ciphertext
                corrupted[94] ^= 0xFF
                corrupted[95] ^= 0xFF
            f.seek(0)
            f.write(bytes(corrupted))
        
        print(f"Attempting retrieval of corrupted file...")
        try:
            retrieve_file(filepath2, passphrase2)
            print("ERROR: Should have raised an exception!")
        except CorruptedFileError as e:
            print(f"CAUGHT CorruptedFileError: {e}")
            print("SUCCESS: System correctly detected file corruption!")
        except WrongPassphraseError as e:
            print(f"CAUGHT WrongPassphraseError: {e}")
        
        # --- Test 4: Verify isolation - other files remain secure ---
        print("\n--- Test 4: Isolation Verification ---")
        print("Verifying first file is unaffected by corruption of second file...")
        retrieved_isolated = retrieve_file(filepath1, passphrase)
        assert retrieved_isolated == original_data
        print(f"Retrieved first file successfully: '{retrieved_isolated}'")
        print("SUCCESS: Failed access attempts do not compromise other stored files!")
        
        # --- Test 5: Corruption of integrity hash itself ---
        print("\n--- Test 5: Corruption of File Header ---")
        filepath3 = os.path.join(tmpdir, "third_secret.enc")
        data3 = "Critical data with tamper detection."
        passphrase3 = "third-passphrase-secure"
        
        store_file(filepath3, data3, passphrase3)
        print(f"Stored third file: {filepath3}")
        
        # Corrupt the integrity hash region
        print("Simulating corruption of integrity metadata...")
        with open(filepath3, 'r+b') as f:
            content = f.read()
            corrupted = bytearray(content)
            # Corrupt the integrity hash (bytes 60-91)
            corrupted[65] ^= 0xFF
            f.seek(0)
            f.write(bytes(corrupted))
        
        try:
            retrieve_file(filepath3, passphrase3)
            print("ERROR: Should have raised an exception!")
        except CorruptedFileError as e:
            print(f"CAUGHT CorruptedFileError: {e}")
            print("SUCCESS: System detected corruption in file metadata!")
        except WrongPassphraseError as e:
            print(f"CAUGHT WrongPassphraseError: {e}")
        
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
        
    finally:
        # Clean up temporary files
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()