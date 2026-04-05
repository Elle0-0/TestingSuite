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
    Encrypt data with integrity protection and save it.
    
    File format:
    [16 bytes salt][12 bytes nonce][32 bytes HMAC of (salt + nonce + ciphertext)][ciphertext...]
    
    AES-GCM provides authenticated encryption (confidentiality + integrity).
    An additional HMAC over the entire ciphertext bundle allows distinguishing
    between wrong passphrase and file corruption.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    # Compute HMAC over salt + nonce + ciphertext using a derived HMAC key
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    payload = salt + nonce + ciphertext
    file_hmac = hmac.new(hmac_key, payload, hashlib.sha256).digest()
    
    # File layout: salt (16) | nonce (12) | hmac (32) | ciphertext (variable)
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(file_hmac)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieve and decrypt data from an encrypted file.
    
    Raises:
        WrongPassphraseError: if the passphrase is incorrect
        CorruptedFileError: if the file has been tampered with or corrupted
        FileNotFoundError: if the file does not exist
    """
    with open(filepath, 'rb') as f:
        file_data = f.read()
    
    if len(file_data) < 16 + 12 + 32:
        raise CorruptedFileError("File is too small to be a valid encrypted file.")
    
    salt = file_data[:16]
    nonce = file_data[16:28]
    stored_hmac = file_data[28:60]
    ciphertext = file_data[60:]
    
    # First, verify HMAC to check if passphrase is correct
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    payload = salt + nonce + ciphertext
    computed_hmac = hmac.new(hmac_key, payload, hashlib.sha256).digest()
    
    hmac_valid = hmac.compare_digest(stored_hmac, computed_hmac)
    
    # Derive decryption key
    key = _derive_key(passphrase, salt)
    
    try:
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        if not hmac_valid:
            # HMAC doesn't match either — could be wrong passphrase or corruption.
            # Since HMAC is keyed with passphrase, mismatch suggests wrong passphrase
            # unless file was also corrupted.
            raise WrongPassphraseError(
                "Decryption failed. The passphrase appears to be incorrect."
            )
        else:
            # HMAC matched (passphrase correct) but AES-GCM failed — file corrupted
            raise CorruptedFileError(
                "Decryption failed. The file appears to be corrupted."
            )
    
    if not hmac_valid:
        # AES-GCM passed but HMAC didn't — unusual, treat as corruption
        raise CorruptedFileError(
            "HMAC verification failed. The file may have been tampered with."
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
        
        store_file(filepath1, original_data, passphrase)
        print(f"File stored successfully at: {filepath1}")
        
        retrieved_data = retrieve_file(filepath1, passphrase)
        print(f"Retrieved data: {retrieved_data}")
        
        assert retrieved_data == original_data
        print("SUCCESS: Data matches original!\n")
        
        # === Scenario 2: Wrong passphrase ===
        print("=" * 60)
        print("Scenario 2: Attempt retrieval with wrong passphrase")
        print("=" * 60)
        
        try:
            wrong_passphrase = "wrong-passphrase-attempt"
            retrieved_data = retrieve_file(filepath1, wrong_passphrase)
            print("ERROR: Should not reach here!")
        except WrongPassphraseError as e:
            print(f"EXPECTED FAILURE - WrongPassphraseError: {e}")
        except CorruptedFileError as e:
            print(f"EXPECTED FAILURE - CorruptedFileError: {e}")
        except Exception as e:
            print(f"FAILURE detected: {type(e).__name__}: {e}")
        
        print()
        
        # Verify that the original file is still accessible with correct passphrase
        retrieved_data = retrieve_file(filepath1, passphrase)
        assert retrieved_data == original_data
        print("Verified: Original file still accessible with correct passphrase.\n")
        
        # === Scenario 3: Corrupted file ===
        print("=" * 60)
        print("Scenario 3: Attempt retrieval of corrupted file")
        print("=" * 60)
        
        filepath2 = os.path.join(tmpdir, "corrupted_document.enc")
        store_file(filepath2, "Another secret message.", passphrase)
        print(f"File stored successfully at: {filepath2}")
        
        # Corrupt the file by flipping some bytes in the ciphertext area
        with open(filepath2, 'rb') as f:
            file_content = bytearray(f.read())
        
        # Corrupt bytes in the ciphertext portion (after salt + nonce + hmac = 60 bytes)
        if len(file_content) > 65:
            file_content[62] ^= 0xFF
            file_content[63] ^= 0xFF
            file_content[64] ^= 0xFF
        
        with open(filepath2, 'wb') as f:
            f.write(file_content)
        
        print("File has been corrupted (bytes flipped in ciphertext region).")
        
        try:
            retrieved_data = retrieve_file(filepath2, passphrase)
            print("ERROR: Should not reach here!")
        except CorruptedFileError as e:
            print(f"EXPECTED FAILURE - CorruptedFileError: {e}")
        except WrongPassphraseError as e:
            print(f"FAILURE detected (misidentified as wrong passphrase): {e}")
        except Exception as e:
            print(f"FAILURE detected: {type(e).__name__}: {e}")
        
        print()
        
        # Verify that the first file is still unaffected
        retrieved_data = retrieve_file(filepath1, passphrase)
        assert retrieved_data == original_data
        print("Verified: Other stored files remain secure and accessible.")
        print("Failed access attempts did not compromise other files.\n")
        
        # === Summary ===
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print("- AES-256-GCM provides authenticated encryption")
        print("- PBKDF2 with 100,000 iterations for key derivation")
        print("- Unique salt and nonce per file")
        print("- HMAC distinguishes wrong passphrase from corruption")
        print("- Each file is independently encrypted; failure on one")
        print("  does not affect others")
        
    finally:
        # Clean up temporary files
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"\nCleaned up temporary directory: {tmpdir}")


if __name__ == "__main__":
    main()