import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

_BACKEND = default_backend()
_SALT_SIZE = 16
_NONCE_SIZE = 12
_KEY_SIZE_BYTES = 32
_PBKDF2_ITERATIONS = 100_000

class IntegrityError(Exception):
    """Custom exception for decryption or integrity check failures."""
    pass

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a cryptographic key from a passphrase and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_SIZE_BYTES,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
        backend=_BACKEND
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data with integrity protection and saves it to a file.

    The file format is: [salt][nonce][encrypted_data_with_tag]
    """
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    
    data_bytes = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieves and decrypts data from a file, verifying its integrity.

    Raises:
        IntegrityError: If the passphrase is incorrect or the file is corrupted.
        FileNotFoundError: If the specified file does not exist.
    """
    try:
        with open(filepath, 'rb') as f:
            file_content = f.read()

        if len(file_content) < (_SALT_SIZE + _NONCE_SIZE):
            raise IntegrityError("File is corrupted or invalid.")

        salt = file_content[:_SALT_SIZE]
        nonce = file_content[_SALT_SIZE:_SALT_SIZE + _NONCE_SIZE]
        ciphertext = file_content[_SALT_SIZE + _NONCE_SIZE:]
        
        key = _derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_data.decode('utf-8')

    except InvalidTag:
        raise IntegrityError("Failed to retrieve file: incorrect passphrase or file is corrupted.")
    except (ValueError, IndexError):
        raise IntegrityError("File is corrupted or has an invalid format.")


def main():
    """Demonstrates secure file storage and retrieval with integrity checks."""
    filepath = "secure_document.bin"
    passphrase = "super_secret_password_123"
    wrong_passphrase = "wrong_password"
    original_data = "This is a highly confidential message. Handle with care."

    # 1. Successful storage and retrieval
    print("--- 1. Testing successful storage and retrieval ---")
    try:
        store_file(filepath, original_data, passphrase)
        print(f"File '{filepath}' stored successfully.")
        
        retrieved_data = retrieve_file(filepath, passphrase)
        print("File retrieved and decrypted successfully.")
        print(f"Retrieved data: '{retrieved_data}'")
        assert original_data == retrieved_data
    except (IntegrityError, FileNotFoundError) as e:
        print(f"An unexpected error occurred: {e}")
    print("-" * 50)

    # 2. Failed retrieval with wrong passphrase
    print("\n--- 2. Testing retrieval with a wrong passphrase ---")
    try:
        print(f"Attempting to retrieve '{filepath}' with a wrong passphrase...")
        retrieve_file(filepath, wrong_passphrase)
    except IntegrityError as e:
        print(f"Caught expected exception: {e}")
    print("-" * 50)

    # 3. Failed retrieval with corrupted file
    print("\n--- 3. Testing retrieval with a corrupted file ---")
    try:
        print(f"Corrupting file '{filepath}'...")
        with open(filepath, 'r+b') as f:
            content = bytearray(f.read())
            # Flip a bit in the middle of the ciphertext
            corruption_index = len(content) // 2
            content[corruption_index] ^= 0xFF 
            f.seek(0)
            f.write(content)
        
        print("Attempting to retrieve the corrupted file...")
        retrieve_file(filepath, passphrase)
    except IntegrityError as e:
        print(f"Caught expected exception: {e}")
    except FileNotFoundError:
        print("File not found for corruption test.")
    finally:
        # Cleanup
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"\nCleaned up file: '{filepath}'")

if __name__ == "__main__":
    main()