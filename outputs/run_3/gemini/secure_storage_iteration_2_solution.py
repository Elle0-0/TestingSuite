import os
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet, InvalidToken

SALT_SIZE = 16
KDF_ITERATIONS = 100_000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data.encode())
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(encrypted_data)

def retrieve_file(filepath: str, passphrase: str) -> str:
    try:
        with open(filepath, 'rb') as f:
            salt = f.read(SALT_SIZE)
            encrypted_data = f.read()

        key = _derive_key(passphrase, salt)
        fernet = Fernet(key)
        
        decrypted_data = fernet.decrypt(encrypted_data)
        return decrypted_data.decode()
    except (FileNotFoundError, IOError) as e:
        raise e
    except InvalidToken as e:
        raise e
    except Exception as e:
        raise InvalidToken("Failed to decrypt file. It may be corrupted or an unknown error occurred.") from e

def main():
    TEST_FILE = "secure_data.bin"
    CORRUPT_FILE = "corrupt_data.bin"
    GOOD_PASSPHRASE = "correct horse battery staple"
    BAD_PASSPHRASE = "wrong horse battery staple"
    SAMPLE_DATA = "The crow flies at midnight."

    print("--- 1. DEMONSTRATING SUCCESSFUL STORAGE AND RETRIEVAL ---")
    try:
        store_file(TEST_FILE, SAMPLE_DATA, GOOD_PASSPHRASE)
        print(f"File '{TEST_FILE}' stored successfully.")
        
        retrieved_data = retrieve_file(TEST_FILE, GOOD_PASSPHRASE)
        print(f"File '{TEST_FILE}' retrieved successfully.")
        print(f"Original data:  '{SAMPLE_DATA}'")
        print(f"Retrieved data: '{retrieved_data}'")
        assert retrieved_data == SAMPLE_DATA
        print("Data integrity confirmed.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print("\n--- 2. DEMONSTRATING FAILED RETRIEVAL (WRONG PASSPHRASE) ---")
    try:
        print(f"Attempting to retrieve '{TEST_FILE}' with a bad passphrase...")
        retrieve_file(TEST_FILE, BAD_PASSPHRASE)
    except InvalidToken:
        print("Success: Caught expected error for wrong passphrase.")
        print("System correctly identified an invalid passphrase or corrupted data.")
    except Exception as e:
        print(f"Caught an unexpected error type: {type(e).__name__}")

    print("\n--- 3. DEMONSTRATING FAILED RETRIEVAL (CORRUPTED FILE) ---")
    try:
        store_file(CORRUPT_FILE, SAMPLE_DATA, GOOD_PASSPHRASE)
        print(f"File '{CORRUPT_FILE}' stored successfully for corruption test.")
        
        with open(CORRUPT_FILE, "r+b") as f:
            f.seek(SALT_SIZE + 10) 
            f.write(b'X')
        print(f"Manually corrupted '{CORRUPT_FILE}'.")
        
        print(f"Attempting to retrieve corrupted file '{CORRUPT_FILE}'...")
        retrieve_file(CORRUPT_FILE, GOOD_PASSPHRASE)
    except InvalidToken:
        print("Success: Caught expected error for corrupted file.")
        print("System correctly identified an invalid passphrase or corrupted data.")
    except Exception as e:
        print(f"Caught an unexpected error type: {type(e).__name__}")
        
    finally:
        print("\n--- CLEANUP ---")
        for f in [TEST_FILE, CORRUPT_FILE]:
            if os.path.exists(f):
                os.remove(f)
                print(f"Removed '{f}'.")

if __name__ == "__main__":
    main()