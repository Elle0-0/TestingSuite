import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
# NIST recommends at least 10,000 iterations for PBKDF2.
# 480,000 is a reasonably strong modern default.
ITERATIONS = 480000

class SecureStorageError(Exception):
    """Custom exception for storage or retrieval failures."""
    pass

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a key from a passphrase and salt using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data with integrity protection and saves it to a file.

    The file format is: [16-byte salt][12-byte nonce][encrypted data + auth tag]
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    plaintext = data.encode('utf-8')
    # AES-GCM provides Authenticated Encryption with Associated Data (AEAD).
    # The 'encrypt' method returns the ciphertext with the authentication tag appended.
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    try:
        with open(filepath, 'wb') as f:
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)
    except IOError as e:
        raise SecureStorageError(f"Failed to write to file: {e}") from e

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieves and decrypts data from a file, verifying its integrity.

    Raises:
        SecureStorageError: If the file is not found, corrupted, or if the
                            passphrase is incorrect.
    """
    try:
        with open(filepath, 'rb') as f:
            salt = f.read(SALT_SIZE)
            nonce = f.read(NONCE_SIZE)
            ciphertext = f.read()

        if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE or not ciphertext:
            raise SecureStorageError("File is malformed or empty.")

    except FileNotFoundError:
        raise SecureStorageError(f"File not found: {filepath}")
    except IOError as e:
        raise SecureStorageError(f"Failed to read file: {e}") from e

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    
    try:
        # 'decrypt' will verify the authentication tag automatically.
        # If the key is wrong (wrong passphrase) or the ciphertext/tag has
        # been tampered with, it will raise an InvalidTag exception.
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode('utf-8')
    except InvalidTag:
        # It's crucial not to distinguish between a wrong passphrase and a
        # corrupted file to avoid leaking information.
        raise SecureStorageError("Decryption failed: incorrect passphrase or corrupted file.")
    except Exception as e:
        raise SecureStorageError(f"An unexpected error occurred during retrieval: {e}") from e

def main():
    """Demonstrates secure storage and retrieval scenarios."""
    FILEPATH = "secure_document.dat"
    CORRUPTED_FILEPATH = "corrupted_document.dat"
    PASSPHRASE = "super_secret_password_123!"
    WRONG_PASSPHRASE = "wrong_password"
    DATA = "This is the confidential data that needs to be stored securely."

    try:
        # 1. Demonstrate successful storage and retrieval
        print("--- 1. Successful Storage and Retrieval ---")
        store_file(FILEPATH, DATA, PASSPHRASE)
        print(f"File '{FILEPATH}' stored successfully.")
        
        retrieved_data = retrieve_file(FILEPATH, PASSPHRASE)
        print(f"File '{FILEPATH}' retrieved successfully.")
        print(f"Retrieved data: '{retrieved_data}'")
        assert retrieved_data == DATA
        print("Success: Retrieved data matches original data.\n")

        # 2. Demonstrate a failed attempt with the wrong passphrase
        print("--- 2. Failed Retrieval (Wrong Passphrase) ---")
        try:
            print(f"Attempting to retrieve '{FILEPATH}' with a wrong passphrase...")
            retrieve_file(FILEPATH, WRONG_PASSPHRASE)
        except SecureStorageError as e:
            print(f"Caught expected exception: {e}\n")

        # 3. Demonstrate a failed attempt with a corrupted file
        print("--- 3. Failed Retrieval (Corrupted File) ---")
        try:
            # Create a corrupted file by altering one byte of the ciphertext
            with open(FILEPATH, 'rb') as f_orig:
                original_content = bytearray(f_orig.read())
            
            # Corrupt the last byte of the file (part of the auth tag)
            original_content[-1] ^= 0xFF 
            
            with open(CORRUPTED_FILEPATH, 'wb') as f_corr:
                f_corr.write(original_content)
            print(f"Created a corrupted version of the file: '{CORRUPTED_FILEPATH}'")

            print(f"Attempting to retrieve '{CORRUPTED_FILEPATH}' with the correct passphrase...")
            retrieve_file(CORRUPTED_FILEPATH, PASSPHRASE)
        except SecureStorageError as e:
            print(f"Caught expected exception: {e}\n")

    except SecureStorageError as e:
        print(f"An unexpected top-level error occurred: {e}")
    finally:
        # Clean up created files
        for f in [FILEPATH, CORRUPTED_FILEPATH]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    main()