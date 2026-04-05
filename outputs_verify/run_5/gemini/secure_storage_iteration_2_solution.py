import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet, InvalidToken

class SecureStorageError(Exception):
    """Custom exception for storage-related errors like corruption or wrong passphrase."""
    pass

SALT_SIZE = 16
KDF_ITERATIONS = 480_000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a Fernet-compatible key from a passphrase and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
    return key

def store_file(filepath: str, data: str, passphrase:str) -> None:
    """
    Encrypts data with integrity protection and saves it to a file.
    The file format is: 16-byte salt + encrypted data.
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data.encode('utf-8'))

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(encrypted_data)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieves and decrypts data from a file, verifying its integrity.

    Returns:
        The original data as a string on success.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        SecureStorageError: If the passphrase is incorrect or the file is corrupted.
    """
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        encrypted_data = f.read()

    if len(salt) != SALT_SIZE or not encrypted_data:
        raise SecureStorageError("Failed to retrieve file: file is corrupted.")

    try:
        key = _derive_key(passphrase, salt)
        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode('utf-8')
    except InvalidToken:
        raise SecureStorageError("Failed to retrieve file: incorrect passphrase or file has been corrupted.")

def main():
    """
    Demonstrates the secure storage and retrieval functionality, including failure cases.
    """
    FILE_PATH = "my_secure_file.dat"
    PASSPHRASE = "super-secret-passphrase-123"
    WRONG_PASSPHRASE = "this-is-not-the-passphrase"
    DATA = "This is a highly confidential message that needs integrity."

    print("--- Secure Storage Demo ---")

    # --- 1. Successful store and retrieve ---
    print("\n[DEMO 1: Successful Storage and Retrieval]")
    try:
        store_file(FILE_PATH, DATA, PASSPHRASE)
        print(f"File '{FILE_PATH}' stored successfully.")

        retrieved_data = retrieve_file(FILE_PATH, PASSPHRASE)
        print("File retrieved successfully.")
        print(f"  - Original data:    '{DATA}'")
        print(f"  - Retrieved data:   '{retrieved_data}'")
        assert DATA == retrieved_data
    except (SecureStorageError, FileNotFoundError) as e:
        print(f"An unexpected error occurred: {e}")

    # --- 2. Failed retrieval with wrong passphrase ---
    print("\n[DEMO 2: Failed Retrieval (Wrong Passphrase)]")
    try:
        print(f"Attempting to retrieve '{FILE_PATH}' with a wrong passphrase...")
        retrieve_file(FILE_PATH, WRONG_PASSPHRASE)
    except SecureStorageError as e:
        print(f"Caught expected exception: {e}")

    # --- 3. Failed retrieval with corrupted file ---
    print("\n[DEMO 3: Failed Retrieval (Corrupted File)]")
    try:
        # Manually corrupt the file by flipping a bit in the ciphertext
        with open(FILE_PATH, "r+b") as f:
            f.seek(SALT_SIZE + 20)  # Go somewhere into the ciphertext
            original_byte = f.read(1)
            flipped_byte = bytes([original_byte[0] ^ 0b00000001])
            f.seek(-1, os.SEEK_CUR)
            f.write(flipped_byte)
        print(f"File '{FILE_PATH}' has been intentionally corrupted.")

        print("Attempting to retrieve the corrupted file with the correct passphrase...")
        retrieve_file(FILE_PATH, PASSPHRASE)
    except SecureStorageError as e:
        print(f"Caught expected exception: {e}")
    finally:
        # Clean up the test file
        if os.path.exists(FILE_PATH):
            os.remove(FILE_PATH)
            print(f"\nCleanup: Removed '{FILE_PATH}'.")

if __name__ == "__main__":
    main()