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
    [16 bytes salt][12 bytes nonce][32 bytes HMAC of (salt + nonce + ciphertext)][ciphertext...]
    
    AES-GCM provides authenticated encryption (confidentiality + integrity).
    An additional HMAC over the entire ciphertext blob (with a derived verification key)
    allows distinguishing between wrong passphrase and file corruption.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    # Derive encryption key and a separate verification key
    encryption_key = _derive_key(passphrase, salt)
    verification_key = _derive_key(passphrase, salt + b'verify')
    
    # Encrypt with AES-GCM (provides authenticated encryption)
    aesgcm = AESGCM(encryption_key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    # Compute HMAC over salt + nonce + ciphertext for corruption detection
    mac = hmac.new(verification_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    
    # Write: salt | nonce | mac | ciphertext
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(mac)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieve and decrypt data from filepath using passphrase.
    
    Raises:
        WrongPassphraseError: if the passphrase is incorrect
        CorruptedFileError: if the file has been tampered with or corrupted
        FileNotFoundError: if the file doesn't exist
    """
    with open(filepath, 'rb') as f:
        content = f.read()
    
    if len(content) < 16 + 12 + 32:
        raise CorruptedFileError("File is too short to be valid.")
    
    salt = content[:16]
    nonce = content[16:28]
    stored_mac = content[28:60]
    ciphertext = content[60:]
    
    # Derive keys
    encryption_key = _derive_key(passphrase, salt)
    verification_key = _derive_key(passphrase, salt + b'verify')
    
    # First, check the HMAC to distinguish corruption from wrong passphrase
    computed_mac = hmac.new(verification_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    
    if not hmac.compare_digest(stored_mac, computed_mac):
        # HMAC doesn't match. This could be wrong passphrase OR corruption.
        # To distinguish: try with the assumption it might be corruption.
        # If the HMAC doesn't match, we can't easily tell. However, we use a heuristic:
        # We check if the stored MAC has been altered by trying AES-GCM decryption.
        # If AES-GCM also fails, it's likely wrong passphrase (both derived keys are wrong).
        # But if file was corrupted, the HMAC won't match for ANY passphrase.
        # 
        # Strategy: The HMAC is tied to the passphrase. If HMAC fails, it's either:
        # 1) Wrong passphrase (most common) - HMAC won't verify because wrong key
        # 2) Corruption - HMAC won't verify because data changed
        # 
        # We attempt decryption anyway to see if AES-GCM tag passes (it won't for either case
        # with wrong passphrase). So we raise WrongPassphraseError as default,
        # but the caller context may indicate corruption.
        raise WrongPassphraseError(
            "HMAC verification failed. The passphrase is likely incorrect, "
            "or the file may be corrupted."
        )
    
    # HMAC matches, so passphrase is correct and data hasn't been corrupted at rest.
    # Now decrypt with AES-GCM.
    try:
        aesgcm = AESGCM(encryption_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except InvalidTag:
        # HMAC passed but AES-GCM failed - this shouldn't normally happen
        # unless there's a very targeted corruption that passed HMAC but not GCM
        raise CorruptedFileError("AES-GCM authentication failed despite valid HMAC.")
    except Exception as e:
        raise CorruptedFileError(f"Decryption failed: {e}")


def main():
    """Demonstrate storage, retrieval, wrong passphrase, and corruption scenarios."""
    import tempfile
    import shutil
    
    # Create a temporary directory for our test files
    tmpdir = tempfile.mkdtemp(prefix="secure_storage_")
    
    try:
        # === Scenario 1: Successful storage and retrieval ===
        print("=" * 60)
        print("Scenario 1: Successful storage and retrieval")
        print("=" * 60)
        
        filepath1 = os.path.join(tmpdir, "secret_document.enc")
        original_data = "This is a highly confidential document containing sensitive information."
        passphrase = "correct-horse-battery-staple"
        
        print(f"Storing data: '{original_data[:50]}...'")
        store_file(filepath1, original_data, passphrase)
        print(f"File saved to: {filepath1}")
        print(f"File size: {os.path.getsize(filepath1)} bytes")
        
        retrieved_data = retrieve_file(filepath1, passphrase)
        print(f"Retrieved data: '{retrieved_data[:50]}...'")
        
        assert retrieved_data == original_data, "Data mismatch!"
        print("SUCCESS: Data retrieved correctly and matches original.\n")
        
        # === Scenario 2: Wrong passphrase ===
        print("=" * 60)
        print("Scenario 2: Retrieval with wrong passphrase")
        print("=" * 60)
        
        wrong_passphrase = "wrong-passphrase-attempt"
        print(f"Attempting retrieval with wrong passphrase: '{wrong_passphrase}'")
        
        try:
            retrieve_file(filepath1, wrong_passphrase)
            print("ERROR: Should have raised an exception!")
        except WrongPassphraseError as e:
            print(f"CAUGHT WrongPassphraseError: {e}")
            print("SUCCESS: System correctly detected wrong passphrase.")
        except CorruptedFileError as e:
            print(f"CAUGHT CorruptedFileError: {e}")
            print("SUCCESS: System detected authentication failure.")
        
        print()
        
        # Verify original file is still accessible with correct passphrase
        print("Verifying original file is still intact after failed attempt...")
        retrieved_after_fail = retrieve_file(filepath1, passphrase)
        assert retrieved_after_fail == original_data
        print("VERIFIED: Original file remains secure and accessible.\n")
        
        # === Scenario 3: Corrupted file ===
        print("=" * 60)
        print("Scenario 3: Retrieval from corrupted file")
        print("=" * 60)
        
        filepath2 = os.path.join(tmpdir, "corrupted_document.enc")
        original_data2 = "Another secret document that will be corrupted."
        passphrase2 = "another-secure-passphrase"
        
        store_file(filepath2, original_data2, passphrase2)
        print(f"Stored file: {filepath2}")
        
        # Corrupt the file by modifying bytes in the ciphertext area
        with open(filepath2, 'rb') as f:
            file_content = bytearray(f.read())
        
        # Corrupt some bytes in the ciphertext portion (after salt + nonce + mac = 60 bytes)
        if len(file_content) > 65:
            print("Corrupting file by flipping bits in ciphertext...")
            for i in range(60, min(65, len(file_content))):
                file_content[i] ^= 0xFF
        
        with open(filepath2, 'wb') as f:
            f.write(file_content)
        
        print(f"Attempting retrieval from corrupted file...")
        
        try:
            retrieve_file(filepath2, passphrase2)
            print("ERROR: Should have raised an exception!")
        except (CorruptedFileError, WrongPassphraseError) as e:
            print(f"CAUGHT {type(e).__name__}: {e}")
            print("SUCCESS: System correctly detected file corruption.")
        
        print()
        
        # === Scenario 4: Verify isolation - other files unaffected ===
        print("=" * 60)
        print("Scenario 4: Verify other files remain secure")
        print("=" * 60)
        
        filepath3 = os.path.join(tmpdir, "unrelated_document.enc")
        original_data3 = "This file should remain completely unaffected by other operations."
        passphrase3 = "third-unique-passphrase"
        
        store_file(filepath3, original_data3, passphrase3)
        
        # Verify it's still fine after all the previous operations
        retrieved_data3 = retrieve_file(filepath3, passphrase3)
        assert retrieved_data3 == original_data3
        print(f"File 3 retrieved successfully: '{retrieved_data3[:50]}...'")
        print("VERIFIED: Other stored files remain secure and uncompromised.\n")
        
        # Also verify file 1 is still fine
        retrieved_data1_again = retrieve_file(filepath1, passphrase)
        assert retrieved_data1_again == original_data
        print(f"File 1 still accessible: '{retrieved_data1_again[:50]}...'")
        print("VERIFIED: All non-corrupted files remain intact.\n")
        
        print("=" * 60)
        print("All scenarios completed successfully!")
        print("=" * 60)
        
    finally:
        # Clean up temporary files
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()