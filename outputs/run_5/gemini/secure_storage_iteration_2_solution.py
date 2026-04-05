import os
import shutil
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
KEY_SIZE = 32
ITERATIONS = 100_000
NONCE_SIZE = 12

class IntegrityCheckFailedError(Exception):
    """Raised when decryption fails due to an invalid passphrase or corrupted file."""
    pass

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend()
    )
    key = kdf.derive(passphrase.encode('utf-8'))

    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)

    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, 'rb') as f:
            salt = f.read(SALT_SIZE)
            nonce = f.read(NONCE_SIZE)
            ciphertext = f.read()

        if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE:
             raise IntegrityCheckFailedError("File is malformed or incomplete.")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=ITERATIONS,
            backend=default_backend()
        )
        key = kdf.derive(passphrase.encode('utf-8'))

        aesgcm = AESGCM(key)

        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext_bytes.decode('utf-8')

    except (InvalidTag, FileNotFoundError) as e:
        raise IntegrityCheckFailedError("Failed to retrieve file: invalid passphrase or file is corrupted.") from e

def main():
    test_filepath = "secure_file.dat"
    corrupted_filepath = "corrupted_file.dat"
    passphrase = "super_secret_password_123"
    wrong_passphrase = "wrong_password"
    data_to_store = "This is a highly confidential message."

    # --- 1. Successful storage and retrieval ---
    print("--- 1. Testing successful storage and retrieval ---")
    try:
        store_file(test_filepath, data_to_store, passphrase)
        print(f"File '{test_filepath}' stored successfully.")

        retrieved_data = retrieve_file(test_filepath, passphrase)
        print(f"File '{test_filepath}' retrieved successfully.")
        print(f"Retrieved data: '{retrieved_data}'")
        assert data_to_store == retrieved_data
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    print("-" * 50)

    # --- 2. Failed attempt with wrong passphrase ---
    print("--- 2. Testing failed retrieval with wrong passphrase ---")
    try:
        retrieve_file(test_filepath, wrong_passphrase)
    except IntegrityCheckFailedError as e:
        print(f"Successfully caught expected error: {e}")
    except Exception as e:
        print(f"Caught an unexpected error type: {type(e).__name__} - {e}")
    print("-" * 50)

    # --- 3. Failed attempt with a corrupted file ---
    print("--- 3. Testing failed retrieval with a corrupted file ---")
    try:
        shutil.copy(test_filepath, corrupted_filepath)

        with open(corrupted_filepath, "r+b") as f:
            f.seek(SALT_SIZE + NONCE_SIZE + 5)
            original_byte = f.read(1)
            corrupted_byte = (int.from_bytes(original_byte, 'big') ^ 0xFF).to_bytes(1, 'big')
            f.seek(-1, 1)
            f.write(corrupted_byte)

        print(f"File '{corrupted_filepath}' has been intentionally corrupted.")

        retrieve_file(corrupted_filepath, passphrase)
    except IntegrityCheckFailedError as e:
        print(f"Successfully caught expected error: {e}")
    except Exception as e:
        print(f"Caught an unexpected error type: {type(e).__name__} - {e}")
    finally:
        if os.path.exists(test_filepath):
            os.remove(test_filepath)
        if os.path.exists(corrupted_filepath):
            os.remove(corrupted_filepath)
        print("-" * 50)
        print("Cleanup complete.")

if __name__ == "__main__":
    main()