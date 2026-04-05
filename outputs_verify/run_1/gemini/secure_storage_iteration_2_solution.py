import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
PBKDF2_ITERATIONS = 480000

class DecryptionError(Exception):
    """Raised for decryption failures, indicating a wrong passphrase or corrupted file."""
    pass

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    data_bytes = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, data_bytes, None)
    
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
             raise DecryptionError("File is corrupted or has an invalid format.")

        key = _derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode('utf-8')

    except (FileNotFoundError, PermissionError) as e:
        raise e
    except (InvalidTag, ValueError):
        raise DecryptionError("Decryption failed. File may be corrupted or passphrase is wrong.")
    except Exception as e:
        raise DecryptionError(f"An unexpected error occurred: {e}")


def main():
    TEST_FILE = "secret_document.dat"
    CORRUPTED_FILE = "corrupted_secret_document.dat"
    PASSPHRASE = "super-secret-p@ssphr@se-123"
    WRONG_PASSPHRASE = "i-forgot-my-passphrase"
    FILE_DATA = "This is the secure content of the file."

    print("--- Secure Storage: Second Iteration Demonstration ---")

    try:
        # 1. Successful store and retrieve
        print("\n[1] Testing successful storage and retrieval...")
        store_file(TEST_FILE, FILE_DATA, PASSPHRASE)
        print(f"File '{TEST_FILE}' stored successfully.")
        
        retrieved_data = retrieve_file(TEST_FILE, PASSPHRASE)
        print("File retrieved successfully.")
        print(f"   Original data:    '{FILE_DATA}'")
        print(f"   Retrieved data:   '{retrieved_data}'")
        assert retrieved_data == FILE_DATA
        print("   SUCCESS: Data matches.")

        # 2. Failed retrieval with wrong passphrase
        print("\n[2] Testing retrieval with WRONG passphrase...")
        try:
            retrieve_file(TEST_FILE, WRONG_PASSPHRASE)
        except DecryptionError as e:
            print(f"   SUCCESS: Caught expected error: {e}")

        # 3. Failed retrieval with corrupted file
        print("\n[3] Testing retrieval of a CORRUPTED file...")
        # Create a corrupted copy of the file
        with open(TEST_FILE, 'rb') as f_orig, open(CORRUPTED_FILE, 'wb') as f_corr:
            original_content = f_orig.read()
            corrupted_content = original_content[:-5] + b'xxxxx' # Tamper with the end
            f_corr.write(corrupted_content)
        print(f"Created '{CORRUPTED_FILE}' by tampering with '{TEST_FILE}'.")
        
        try:
            retrieve_file(CORRUPTED_FILE, PASSPHRASE)
        except DecryptionError as e:
            print(f"   SUCCESS: Caught expected error: {e}")

    finally:
        print("\n--- Cleaning up created files ---")
        for f in [TEST_FILE, CORRUPTED_FILE]:
            if os.path.exists(f):
                os.remove(f)
                print(f"Removed '{f}'.")

if __name__ == "__main__":
    main()