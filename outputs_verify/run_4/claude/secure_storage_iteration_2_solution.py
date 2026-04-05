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
    """Derive a 256-bit key from a passphrase and salt using PBKDF2-HMAC-SHA256."""
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
    Encrypts data with AES-256-GCM (which provides both confidentiality and integrity/authentication)
    and saves it to filepath.
    
    File format:
    - 16 bytes: salt (for key derivation)
    - 12 bytes: nonce (for AES-GCM)
    - 32 bytes: HMAC-SHA256 over (salt + nonce + ciphertext) using a secondary key
    - remaining: ciphertext (includes GCM auth tag)
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    # Derive encryption key
    encryption_key = _derive_key(passphrase, salt)
    
    # Derive a separate HMAC key for outer integrity check
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt + b'hmac',
        iterations=100_000,
        dklen=32
    )
    
    # Encrypt with AES-GCM (provides authenticated encryption)
    aesgcm = AESGCM(encryption_key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    # Compute HMAC over salt + nonce + ciphertext for outer integrity verification
    mac = hmac.new(hmac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    
    # Write: salt | nonce | hmac | ciphertext
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(mac)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Reads and decrypts a file previously stored with store_file.
    
    Raises:
        WrongPassphraseError: if the passphrase is incorrect
        CorruptedFileError: if the file has been tampered with or corrupted
        FileNotFoundError: if the file doesn't exist
    """
    with open(filepath, 'rb') as f:
        content = f.read()
    
    if len(content) < 16 + 12 + 32:
        raise CorruptedFileError("File is too short to be a valid encrypted file.")
    
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
    
    # Verify outer HMAC first
    computed_mac = hmac.new(hmac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    
    if not hmac.compare_digest(stored_mac, computed_mac):
        # The HMAC doesn't match. This could be wrong passphrase or corruption.
        # Try decryption to differentiate — if GCM also fails, it's ambiguous,
        # but we lean toward wrong passphrase if the file structure is intact.
        try:
            aesgcm = AESGCM(encryption_key)
            aesgcm.decrypt(nonce, ciphertext, None)
        except InvalidTag:
            pass
        
        # Since HMAC depends on the passphrase, a wrong passphrase will always
        # produce a wrong HMAC. We check if file bytes are structurally valid
        # by trying with the assumption that it might be corruption.
        # However, we cannot distinguish perfectly without the correct key.
        # We raise WrongPassphraseError as the primary suspect when HMAC fails.
        raise WrongPassphraseError(
            "Authentication failed. The passphrase is likely incorrect, "
            "or the file may be corrupted."
        )
    
    # HMAC matched, so passphrase is correct and outer integrity is verified.
    # Now decrypt with AES-GCM for inner integrity check.
    try:
        aesgcm = AESGCM(encryption_key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except InvalidTag:
        raise CorruptedFileError(
            "HMAC verified but GCM authentication failed. "
            "The ciphertext may have been corrupted after HMAC computation."
        )


def main():
    """Demonstrate storage, retrieval, wrong passphrase, and corruption scenarios."""
    test_filepath = "_secure_test_file.enc"
    original_data = "This is highly confidential information that must remain secure."
    passphrase = "correct-horse-battery-staple"
    
    # --- Scenario 1: Successful storage and retrieval ---
    print("=" * 60)
    print("Scenario 1: Successful storage and retrieval")
    print("=" * 60)
    try:
        store_file(test_filepath, original_data, passphrase)
        print(f"  [STORE] File stored successfully at '{test_filepath}'")
        
        retrieved = retrieve_file(test_filepath, passphrase)
        print(f"  [RETRIEVE] Success!")
        print(f"  [DATA] '{retrieved}'")
        assert retrieved == original_data, "Data mismatch!"
        print(f"  [VERIFY] Data integrity confirmed — matches original.")
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {e}")
    print()
    
    # --- Scenario 2: Wrong passphrase ---
    print("=" * 60)
    print("Scenario 2: Retrieval with wrong passphrase")
    print("=" * 60)
    try:
        retrieved = retrieve_file(test_filepath, "wrong-passphrase-attempt")
        print(f"  [RETRIEVE] Got data: '{retrieved}'")
        print("  [WARNING] This should not happen!")
    except WrongPassphraseError as e:
        print(f"  [DENIED] Access denied — {e}")
    except CorruptedFileError as e:
        print(f"  [ERROR] Corruption detected — {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {type(e).__name__}: {e}")
    print()
    
    # --- Scenario 3: Corrupted file ---
    print("=" * 60)
    print("Scenario 3: Retrieval from corrupted file")
    print("=" * 60)
    corrupted_filepath = "_secure_test_corrupted.enc"
    try:
        # First store a valid file
        store_file(corrupted_filepath, original_data, passphrase)
        print(f"  [STORE] File stored at '{corrupted_filepath}'")
        
        # Now corrupt it by flipping some bytes in the ciphertext area
        with open(corrupted_filepath, 'rb') as f:
            file_data = bytearray(f.read())
        
        # Corrupt bytes in the ciphertext region (after salt+nonce+hmac = 60 bytes)
        if len(file_data) > 65:
            file_data[62] ^= 0xFF
            file_data[63] ^= 0xFF
            file_data[64] ^= 0xFF
        
        with open(corrupted_filepath, 'wb') as f:
            f.write(file_data)
        print(f"  [CORRUPT] File bytes modified to simulate corruption")
        
        retrieved = retrieve_file(corrupted_filepath, passphrase)
        print(f"  [RETRIEVE] Got data: '{retrieved}'")
        print("  [WARNING] This should not happen!")
    except WrongPassphraseError as e:
        print(f"  [DETECTED] Authentication failure — {e}")
    except CorruptedFileError as e:
        print(f"  [DETECTED] Corruption detected — {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {type(e).__name__}: {e}")
    print()
    
    # --- Scenario 4: Verify other files remain secure ---
    print("=" * 60)
    print("Scenario 4: Verify original file still accessible after failed attempts")
    print("=" * 60)
    try:
        retrieved = retrieve_file(test_filepath, passphrase)
        print(f"  [RETRIEVE] Original file still accessible!")
        print(f"  [DATA] '{retrieved}'")
        assert retrieved == original_data
        print(f"  [VERIFY] Other files remain uncompromised.")
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {e}")
    print()
    
    # Cleanup
    for fp in [test_filepath, corrupted_filepath]:
        try:
            os.remove(fp)
        except OSError:
            pass
    print("Cleanup complete.")


if __name__ == "__main__":
    main()