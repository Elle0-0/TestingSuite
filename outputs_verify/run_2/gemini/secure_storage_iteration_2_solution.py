import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

# --- Constants for cryptographic parameters ---
SALT_SIZE = 16
TAG_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32  # For AES-256
KDF_ITERATIONS = 480_000

class IntegrityError(Exception):
    """Raised when data integrity check fails, suggesting file corruption."""
    pass

class AuthenticationError(Exception):
    """Raised when authentication fails, suggesting an incorrect passphrase."""
    pass

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a key from a passphrase and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data with integrity protection and saves it to a file.

    The file format is: salt | nonce | tag | ciphertext
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    data_bytes = data.encode('utf-8')
    
    # aesgcm.encrypt returns a single bytes object: ciphertext + tag
    encrypted_blob = aesgcm.encrypt(nonce, data_bytes, None)

    # The tag is the last TAG_SIZE bytes of the output.
    # The ciphertext is everything before the tag.
    tag = encrypted_blob[-TAG_SIZE:]
    ciphertext = encrypted_blob[:-TAG_SIZE]
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(tag)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieves and decrypts data from a file, verifying its integrity.

    Raises:
        AuthenticationError: If the passphrase is wrong or the file is corrupt.
    """
    try:
        with open(filepath, 'rb') as f:
            salt = f.read(SALT_SIZE)
            nonce = f.read(NONCE_SIZE)
            tag = f.read(TAG_SIZE)
            ciphertext = f.read()

        if len(salt) != SALT_SIZE or len(nonce) != NONCE_SIZE or len(tag) != TAG_SIZE:
             raise AuthenticationError("Decryption failed. The file is malformed or corrupt.")

    except FileNotFoundError:
        raise
    except Exception:
        raise AuthenticationError("Decryption failed. The file is malformed or corrupt.")
        
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    try:
        decrypted_data = aesgcm.decrypt(nonce, ciphertext + tag, None)
        return decrypted_data.decode('utf-8')
    except InvalidTag:
        raise AuthenticationError("Decryption failed. The passphrase may be incorrect or the file may be corrupted.")

def main():
    """
    Demonstrates the secure storage and retrieval functions, including failure cases.
    """
    FILEPATH = "confidential_data.bin"
    GOOD_PASSPHRASE = "super-secret-password-123"
    BAD_PASSPHRASE = "wrong-password"
    ORIGINAL_DATA = "This is a highly confidential message. The launch codes are 000-000-000."

    # --- 1. Successful storage and retrieval ---
    print("--- 1. Testing successful storage and retrieval ---")
    try:
        store_file(FILEPATH, ORIGINAL_DATA, GOOD_PASSPHRASE)
        print(f"File '{FILEPATH}' stored successfully.")
        
        retrieved_data = retrieve_file(FILEPATH, GOOD_PASSPHRASE)
        print(f"File '{FILEPATH}' retrieved successfully.")
        print(f"Retrieved data: '{retrieved_data}'")
        assert retrieved_data == ORIGINAL_DATA
        print("Success: Retrieved data matches original data.\n")
    except (AuthenticationError, FileNotFoundError) as e:
        print(f"An unexpected error occurred: {e}\n")


    # --- 2. Failed attempt with wrong passphrase ---
    print("--- 2. Testing failed retrieval with wrong passphrase ---")
    try:
        retrieve_file(FILEPATH, BAD_PASSPHRASE)
    except AuthenticationError as e:
        print(f"Caught expected exception: {e}")
        print("Success: System correctly identified the access failure.\n")
    except Exception as e:
        print(f"Caught an unexpected exception type: {type(e).__name__}: {e}\n")


    # --- 3. Failed attempt with corrupted file ---
    print("--- 3. Testing failed retrieval with corrupted file ---")
    try:
        # Corrupt the file by flipping a bit in the ciphertext
        with open(FILEPATH, 'r+b') as f:
            f.seek(SALT_SIZE + NONCE_SIZE + TAG_SIZE + 10)  # Go 10 bytes into the ciphertext
            original_byte = f.read(1)
            flipped_byte = bytes([original_byte[0] ^ 0xFF]) # Flip all bits
            f.seek(-1, 1) # Go back one byte
            f.write(flipped_byte)
        print(f"File '{FILEPATH}' has been intentionally corrupted.")

        retrieve_file(FILEPATH, GOOD_PASSPHRASE)
    except AuthenticationError as e:
        print(f"Caught expected exception: {e}")
        print("Success: System correctly identified the file corruption.\n")
    except Exception as e:
        print(f"Caught an unexpected exception type: {type(e).__name__}: {e}\n")


    # --- Cleanup ---
    if os.path.exists(FILEPATH):
        os.remove(FILEPATH)
        print(f"Cleaned up file '{FILEPATH}'.")

if __name__ == "__main__":
    main()