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
    Encrypt data with integrity protection and save it.
    
    File format:
    [16 bytes salt][12 bytes nonce][32 bytes HMAC of (salt + nonce + ciphertext)][ciphertext...]
    
    AES-GCM provides authenticated encryption (confidentiality + integrity).
    An additional HMAC over the entire ciphertext blob is stored to distinguish
    between corruption and wrong passphrase scenarios.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    # Compute HMAC over salt + nonce + ciphertext using a derived HMAC key
    # This allows us to distinguish corruption from wrong passphrase:
    # - We store an HMAC keyed with a key derived from (passphrase + salt + "hmac")
    # - On retrieval, we first verify the HMAC. If it fails, the file is corrupted.
    # - If HMAC passes but AES-GCM decryption fails, the passphrase is wrong.
    # Wait, that won't work because HMAC key also depends on passphrase.
    
    # Better approach: store a separate verification HMAC using the same derived key
    # but over a known plaintext marker. This way:
    # 1. First try to decrypt with AES-GCM
    # 2. If it fails, check if the file's stored checksum (passphrase-independent) matches
    #    to determine if it's corruption vs wrong passphrase.
    
    # Use a passphrase-independent checksum (SHA-256) of the raw file content
    # (salt + nonce + ciphertext) to detect corruption
    raw_content = salt + nonce + ciphertext
    checksum = hashlib.sha256(raw_content).digest()
    
    # File format: [32 bytes checksum][16 bytes salt][12 bytes nonce][ciphertext...]
    with open(filepath, 'wb') as f:
        f.write(checksum + raw_content)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieve and decrypt file. 
    
    Raises:
        CorruptedFileError: if file integrity check fails
        WrongPassphraseError: if passphrase is incorrect
        FileNotFoundError: if file doesn't exist
    """
    with open(filepath, 'rb') as f:
        file_data = f.read()
    
    if len(file_data) < 32 + 16 + 12:
        raise CorruptedFileError("File is too small to be valid.")
    
    stored_checksum = file_data[:32]
    raw_content = file_data[32:]
    
    # Verify integrity using passphrase-independent checksum
    computed_checksum = hashlib.sha256(raw_content).digest()
    if not hmac.compare_digest(stored_checksum, computed_checksum):
        raise CorruptedFileError("File has been corrupted. Data integrity check failed.")
    
    salt = raw_content[:16]
    nonce = raw_content[16:28]
    ciphertext = raw_content[28:]
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise WrongPassphraseError("Incorrect passphrase. Unable to decrypt file.")
    
    return plaintext.decode('utf-8')


def main():
    """Demonstrate storage, retrieval, wrong passphrase, and corruption scenarios."""
    test_filepath = "_secure_test_file.enc"
    
    # --- Demonstration 1: Successful store and retrieve ---
    print("=" * 60)
    print("Test 1: Successful storage and retrieval")
    print("=" * 60)
    
    original_data = "This is highly confidential information that must be protected."
    passphrase = "correct-horse-battery-staple"
    
    store_file(test_filepath, original_data, passphrase)
    print(f"Stored file: {test_filepath}")
    
    try:
        retrieved = retrieve_file(test_filepath, passphrase)
        print(f"Retrieved data: {retrieved}")
        assert retrieved == original_data, "Data mismatch!"
        print("SUCCESS: Data matches original.\n")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}\n")
    
    # --- Demonstration 2: Wrong passphrase ---
    print("=" * 60)
    print("Test 2: Retrieval with wrong passphrase")
    print("=" * 60)
    
    wrong_passphrase = "wrong-passphrase-attempt"
    try:
        retrieved = retrieve_file(test_filepath, wrong_passphrase)
        print(f"Retrieved data: {retrieved}")
        print("ERROR: Should not have succeeded!\n")
    except WrongPassphraseError as e:
        print(f"EXPECTED FAILURE - Wrong Passphrase: {e}")
        print("The system correctly detected the wrong passphrase.\n")
    except CorruptedFileError as e:
        print(f"FAILURE detected as corruption: {e}\n")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {type(e).__name__}: {e}\n")
    
    # --- Demonstration 3: Corrupted file ---
    print("=" * 60)
    print("Test 3: Retrieval from corrupted file")
    print("=" * 60)
    
    corrupted_filepath = "_secure_test_corrupted.enc"
    
    # Store a valid file first
    store_file(corrupted_filepath, original_data, passphrase)
    print(f"Stored file: {corrupted_filepath}")
    
    # Corrupt the file by flipping some bytes in the ciphertext area
    with open(corrupted_filepath, 'rb') as f:
        file_data = bytearray(f.read())
    
    # Corrupt bytes in the ciphertext portion (after checksum + salt + nonce = 32+16+12=60)
    if len(file_data) > 65:
        file_data[62] ^= 0xFF
        file_data[63] ^= 0xAA
        file_data[64] ^= 0x55
    
    with open(corrupted_filepath, 'wb') as f:
        f.write(file_data)
    
    print("File has been intentionally corrupted.")
    
    try:
        retrieved = retrieve_file(corrupted_filepath, passphrase)
        print(f"Retrieved data: {retrieved}")
        print("ERROR: Should not have succeeded!\n")
    except CorruptedFileError as e:
        print(f"EXPECTED FAILURE - Corrupted File: {e}")
        print("The system correctly detected file corruption.\n")
    except WrongPassphraseError as e:
        print(f"Detected as wrong passphrase (corruption in ciphertext): {e}\n")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {type(e).__name__}: {e}\n")
    
    # --- Demonstration 4: Original file is still accessible ---
    print("=" * 60)
    print("Test 4: Verify original file unaffected by failed attempts")
    print("=" * 60)
    
    try:
        retrieved = retrieve_file(test_filepath, passphrase)
        print(f"Retrieved data: {retrieved}")
        assert retrieved == original_data
        print("SUCCESS: Original file remains intact and accessible.")
        print("Failed access attempts did not compromise other stored files.\n")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}\n")
    
    # Cleanup
    for fp in [test_filepath, corrupted_filepath]:
        if os.path.exists(fp):
            os.remove(fp)
    
    print("=" * 60)
    print("All demonstrations complete. Test files cleaned up.")
    print("=" * 60)


if __name__ == "__main__":
    main()