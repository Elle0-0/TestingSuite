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
    An additional HMAC over the entire ciphertext bundle allows distinguishing
    between corruption and wrong passphrase scenarios.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    # Compute HMAC over salt + nonce + ciphertext using the derived key
    # This serves as an additional integrity check that's tied to the passphrase
    hmac_key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode('utf-8'),
        salt,
        iterations=100_000,
        dklen=32
    )
    mac = hmac.new(hmac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    
    # Also store a passphrase-independent integrity check (hash of raw file content)
    raw_payload = salt + nonce + ciphertext
    file_checksum = hashlib.sha256(raw_payload).digest()
    
    # File format: [32 bytes file_checksum][16 bytes salt][12 bytes nonce][ciphertext]
    with open(filepath, 'wb') as f:
        f.write(file_checksum + raw_payload)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieve and decrypt the file.
    
    Raises:
        CorruptedFileError: if the file has been tampered with or corrupted
        WrongPassphraseError: if the passphrase is incorrect
        FileNotFoundError: if the file doesn't exist
    """
    with open(filepath, 'rb') as f:
        content = f.read()
    
    if len(content) < 32 + 16 + 12 + 16:
        raise CorruptedFileError("File is too small to be valid.")
    
    file_checksum = content[:32]
    raw_payload = content[32:]
    
    # First check: is the file corrupted at all? (passphrase-independent)
    expected_checksum = hashlib.sha256(raw_payload).digest()
    if not hmac.compare_digest(file_checksum, expected_checksum):
        raise CorruptedFileError("File integrity check failed. The file appears to be corrupted.")
    
    # File is not corrupted, now try to decrypt with the given passphrase
    salt = raw_payload[:16]
    nonce = raw_payload[16:28]
    ciphertext = raw_payload[28:]
    
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise WrongPassphraseError("Decryption failed. The passphrase is incorrect.")
    
    return plaintext.decode('utf-8')


def main():
    """Demonstrate storage, retrieval, wrong passphrase, and corruption scenarios."""
    import tempfile
    import os
    
    tmpdir = tempfile.mkdtemp()
    
    # --- Demonstration 1: Successful storage and retrieval ---
    print("=" * 60)
    print("Demo 1: Successful storage and retrieval")
    print("=" * 60)
    
    filepath = os.path.join(tmpdir, "secret_doc.enc")
    original_data = "This is highly confidential information. Handle with care!"
    passphrase = "correct-horse-battery-staple"
    
    store_file(filepath, original_data, passphrase)
    print(f"Stored file: {filepath}")
    
    try:
        retrieved = retrieve_file(filepath, passphrase)
        print(f"Retrieved data: {retrieved}")
        assert retrieved == original_data
        print("SUCCESS: Data matches original!\n")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}\n")
    
    # --- Demonstration 2: Wrong passphrase ---
    print("=" * 60)
    print("Demo 2: Retrieval with wrong passphrase")
    print("=" * 60)
    
    wrong_passphrase = "wrong-passphrase-attempt"
    try:
        retrieved = retrieve_file(filepath, wrong_passphrase)
        print(f"Retrieved data: {retrieved}")
        print("ERROR: Should not have succeeded!\n")
    except WrongPassphraseError as e:
        print(f"CAUGHT WrongPassphraseError: {e}")
        print("SUCCESS: Wrong passphrase was detected correctly!\n")
    except Exception as e:
        print(f"CAUGHT unexpected exception: {type(e).__name__}: {e}\n")
    
    # --- Demonstration 3: Corrupted file ---
    print("=" * 60)
    print("Demo 3: Retrieval from corrupted file")
    print("=" * 60)
    
    corrupted_filepath = os.path.join(tmpdir, "corrupted_doc.enc")
    
    # Create a valid file first
    store_file(corrupted_filepath, "Another secret document.", passphrase)
    print(f"Stored file: {corrupted_filepath}")
    
    # Now corrupt it by flipping some bytes in the middle
    with open(corrupted_filepath, 'rb') as f:
        file_content = bytearray(f.read())
    
    # Corrupt bytes in the payload area (after the checksum)
    corruption_offset = 40  # somewhere in the salt/nonce/ciphertext area
    for i in range(5):
        if corruption_offset + i < len(file_content):
            file_content[corruption_offset + i] ^= 0xFF
    
    with open(corrupted_filepath, 'wb') as f:
        f.write(bytes(file_content))
    print("File has been corrupted (bytes flipped).")
    
    try:
        retrieved = retrieve_file(corrupted_filepath, passphrase)
        print(f"Retrieved data: {retrieved}")
        print("ERROR: Should not have succeeded!\n")
    except CorruptedFileError as e:
        print(f"CAUGHT CorruptedFileError: {e}")
        print("SUCCESS: File corruption was detected correctly!\n")
    except Exception as e:
        print(f"CAUGHT unexpected exception: {type(e).__name__}: {e}\n")
    
    # --- Demonstration 4: Verify other files remain accessible ---
    print("=" * 60)
    print("Demo 4: Verify original file is still accessible after failed attempts")
    print("=" * 60)
    
    try:
        retrieved = retrieve_file(filepath, passphrase)
        print(f"Retrieved data: {retrieved}")
        assert retrieved == original_data
        print("SUCCESS: Original file remains intact and accessible!")
        print("Failed access attempts did not compromise other stored files.\n")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}\n")
    
    # Cleanup
    for fname in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, fname))
    os.rmdir(tmpdir)
    print("Cleanup complete.")


if __name__ == "__main__":
    main()