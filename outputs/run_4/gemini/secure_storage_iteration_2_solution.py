import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32
KDF_ITERATIONS = 480000

class SecureStorageError(Exception):
    """Custom exception for secure storage failures."""
    pass

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    key = kdf.derive(passphrase.encode('utf-8'))

    nonce = os.urandom(NONCE_SIZE)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    
    data_bytes = data.encode('utf-8')
    ciphertext = encryptor.update(data_bytes) + encryptor.finalize()
    tag = encryptor.tag

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(tag)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, 'rb') as f:
            salt = f.read(SALT_SIZE)
            nonce = f.read(NONCE_SIZE)
            tag = f.read(TAG_SIZE)
            ciphertext = f.read()

        if not all([salt, nonce, tag, ciphertext]):
             raise SecureStorageError("File is truncated or malformed.")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=KDF_ITERATIONS,
            backend=default_backend()
        )
        key = kdf.derive(passphrase.encode('utf-8'))

        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        
        decrypted_data_bytes = decryptor.update(ciphertext) + decryptor.finalize()
        return decrypted_data_bytes.decode('utf-8')

    except (InvalidTag, ValueError, TypeError):
        raise SecureStorageError("Failed to retrieve file: incorrect passphrase or file is corrupted.")
    except FileNotFoundError:
        raise SecureStorageError(f"File not found at path: {filepath}")

def main():
    FILENAME = "secure_document.bin"
    CORRUPT_FILENAME = "corrupt_document.bin"
    PASSPHRASE = "super-secret-password-123"
    WRONG_PASSPHRASE = "super-secret-password-456"
    FILE_DATA = "This is the confidential data that needs to be protected."

    print("--- Secure Storage Demonstration ---")

    # 1. Successful storage and retrieval
    print("\n[1] Testing successful storage and retrieval...")
    try:
        store_file(FILENAME, FILE_DATA, PASSPHRASE)
        print(f"  - File '{FILENAME}' stored successfully.")
        retrieved_data = retrieve_file(FILENAME, PASSPHRASE)
        print(f"  - File '{FILENAME}' retrieved successfully.")
        if retrieved_data == FILE_DATA:
            print("  - SUCCESS: Retrieved data matches original data.")
        else:
            print("  - FAILURE: Retrieved data does not match original data.")
    except Exception as e:
        print(f"  - An unexpected error occurred: {e}")

    # 2. Failed retrieval with wrong passphrase
    print("\n[2] Testing failed retrieval with a wrong passphrase...")
    try:
        retrieve_file(FILENAME, WRONG_PASSPHRASE)
        print("  - FAILURE: File was retrieved even with the wrong passphrase.")
    except SecureStorageError as e:
        print(f"  - SUCCESS: Caught expected exception: {e}")
    except Exception as e:
        print(f"  - An unexpected error occurred: {e}")

    # 3. Failed retrieval with a corrupted file
    print("\n[3] Testing failed retrieval with a corrupted file...")
    try:
        # Create a valid file first
        store_file(CORRUPT_FILENAME, FILE_DATA, PASSPHRASE)
        
        # Manually corrupt the file
        with open(CORRUPT_FILENAME, 'r+b') as f:
            f.seek(-1, os.SEEK_END)  # Go to the last byte
            last_byte = f.read(1)
            corrupted_byte = (last_byte[0] ^ 0xFF).to_bytes(1, 'big')
            f.seek(-1, os.SEEK_END)
            f.write(corrupted_byte)
        print(f"  - File '{CORRUPT_FILENAME}' has been intentionally corrupted.")

        # Attempt to retrieve with the correct passphrase
        retrieve_file(CORRUPT_FILENAME, PASSPHRASE)
        print("  - FAILURE: Corrupted file was retrieved without error.")
    except SecureStorageError as e:
        print(f"  - SUCCESS: Caught expected exception: {e}")
    except Exception as e:
        print(f"  - An unexpected error occurred: {e}")

    # Clean up generated files
    finally:
        print("\n--- Cleaning up ---")
        for f in [FILENAME, CORRUPT_FILENAME]:
            if os.path.exists(f):
                os.remove(f)
                print(f"  - Removed '{f}'")

if __name__ == "__main__":
    main()