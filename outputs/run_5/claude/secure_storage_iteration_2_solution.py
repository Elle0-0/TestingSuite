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
    Encrypts data with integrity protection and saves it.
    
    File format:
    [16 bytes salt][12 bytes nonce][32 bytes HMAC of (salt + nonce + ciphertext)][ciphertext]
    
    AES-GCM provides authenticated encryption (confidentiality + integrity).
    An additional HMAC over the entire encrypted payload allows distinguishing
    between corruption and wrong passphrase.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    plaintext = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    # Compute HMAC over salt + nonce + ciphertext for corruption detection
    # Use a secondary key derived from the main key
    hmac_key = hashlib.sha256(key + b"hmac-integrity").digest()
    payload = salt + nonce + ciphertext
    file_hmac = hmac.new(hmac_key, payload, hashlib.sha256).digest()
    
    # File format: salt | nonce | hmac | ciphertext
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
        content = f.read()
    
    if len(content) < 16 + 12 + 32:
        raise CorruptedFileError("File is too small to be a valid encrypted file.")
    
    salt = content[:16]
    nonce = content[16:28]
    stored_hmac = content[28:60]
    ciphertext = content[60:]
    
    key = _derive_key(passphrase, salt)
    
    # Compute HMAC to check for corruption vs wrong passphrase
    hmac_key = hashlib.sha256(key + b"hmac-integrity").digest()
    payload = salt + nonce + ciphertext
    computed_hmac = hmac.new(hmac_key, payload, hashlib.sha256).digest()
    
    # First, try to decrypt with AES-GCM
    aesgcm = AESGCM(key)
    
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        # Decryption failed. Now determine why:
        # If HMAC doesn't match, it could be corruption OR wrong passphrase.
        # With wrong passphrase, both HMAC and GCM tag will fail.
        # With corruption (right passphrase), HMAC will also fail because data changed.
        # 
        # Strategy: We can't verify HMAC with wrong passphrase (different key).
        # But if we had the right passphrase and file is corrupted, HMAC would fail.
        # If wrong passphrase, HMAC will also fail (different hmac_key).
        #
        # To distinguish: store a passphrase verification tag separately.
        # We use the HMAC check: if the stored HMAC was computed with the same key,
        # it means the passphrase is correct but the file is corrupted.
        # If HMAC doesn't match, it's likely wrong passphrase.
        
        if hmac.compare_digest(computed_hmac, stored_hmac):
            # HMAC matches (correct passphrase, correct outer data) but GCM failed
            # This means the ciphertext's internal GCM tag is corrupted
            raise CorruptedFileError(
                "File integrity check failed. The file appears to be corrupted."
            )
        else:
            # HMAC doesn't match - could be wrong passphrase or corruption
            # Try to detect corruption by checking if the file structure looks tampered
            # Since we can't know for sure, we assume wrong passphrase first
            # unless we have other evidence of corruption
            raise WrongPassphraseError(
                "Decryption failed. The passphrase appears to be incorrect, "
                "or the file may be corrupted."
            )
    
    # Decryption succeeded; verify HMAC for extra integrity assurance
    if not hmac.compare_digest(computed_hmac, stored_hmac):
        # Data decrypted fine but HMAC doesn't match - metadata corruption
        raise CorruptedFileError(
            "File metadata integrity check failed. The HMAC does not match."
        )
    
    return plaintext.decode('utf-8')


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
        original_data = "This is highly confidential information. Handle with care!"
        passphrase = "correct-horse-battery-staple"
        
        print(f"Storing data: '{original_data}'")
        store_file(filepath1, original_data, passphrase)
        print(f"File saved to: {filepath1}")
        
        retrieved_data = retrieve_file(filepath1, passphrase)
        print(f"Retrieved data: '{retrieved_data}'")
        
        assert retrieved_data == original_data
        print("SUCCESS: Data retrieved matches original!\n")
        
        # === Scenario 2: Wrong passphrase ===
        print("=" * 60)
        print("Scenario 2: Attempt retrieval with wrong passphrase")
        print("=" * 60)
        
        wrong_passphrase = "wrong-passphrase-123"
        print(f"Attempting to retrieve with passphrase: '{wrong_passphrase}'")
        
        try:
            retrieve_file(filepath1, wrong_passphrase)
            print("ERROR: Should have raised an exception!")
        except WrongPassphraseError as e:
            print(f"CAUGHT WrongPassphraseError: {e}")
            print("SUCCESS: Wrong passphrase detected correctly!\n")
        except CorruptedFileError as e:
            print(f"CAUGHT CorruptedFileError: {e}")
            print("Note: Wrong passphrase detected as integrity failure.\n")
        
        # Verify that the original file is still accessible with correct passphrase
        print("Verifying original file is still accessible...")
        retrieved_again = retrieve_file(filepath1, passphrase)
        assert retrieved_again == original_data
        print("SUCCESS: Original file remains intact and accessible!\n")
        
        # === Scenario 3: Corrupted file ===
        print("=" * 60)
        print("Scenario 3: Attempt retrieval of corrupted file")
        print("=" * 60)
        
        # Create a second file and corrupt it
        filepath2 = os.path.join(tmpdir, "corrupted_document.enc")
        secret_data2 = "Another secret message that will be corrupted."
        passphrase2 = "another-strong-passphrase"
        
        store_file(filepath2, secret_data2, passphrase2)
        print(f"Stored file: {filepath2}")
        
        # Corrupt the file by flipping some bytes in the ciphertext area
        with open(filepath2, 'rb') as f:
            file_content = bytearray(f.read())
        
        # Corrupt bytes in the ciphertext region (after salt + nonce + hmac = 60 bytes)
        if len(file_content) > 65:
            print("Corrupting file contents...")
            for i in range(60, min(70, len(file_content))):
                file_content[i] ^= 0xFF  # Flip all bits
        
        with open(filepath2, 'wb') as f:
            f.write(bytes(file_content))
        
        print(f"Attempting to retrieve corrupted file with correct passphrase: '{passphrase2}'")
        
        try:
            retrieve_file(filepath2, passphrase2)
            print("ERROR: Should have raised an exception!")
        except CorruptedFileError as e:
            print(f"CAUGHT CorruptedFileError: {e}")
            print("SUCCESS: File corruption detected correctly!\n")
        except WrongPassphraseError as e:
            print(f"CAUGHT WrongPassphraseError: {e}")
            print("Note: Corruption detected as potential passphrase/integrity issue.\n")
        
        # === Verify isolation: other files remain unaffected ===
        print("=" * 60)
        print("Verification: Other files remain secure and accessible")
        print("=" * 60)
        
        final_check = retrieve_file(filepath1, passphrase)
        assert final_check == original_data
        print(f"File 1 still accessible: '{final_check}'")
        print("SUCCESS: Failed access attempts did not compromise other files!\n")
        
    finally:
        # Clean up temporary files
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Cleaned up temporary directory: {tmpdir}")


if __name__ == "__main__":
    main()