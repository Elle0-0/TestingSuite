import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

class AccessError(Exception):
    """Custom exception for decryption or integrity errors."""
    pass

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_ITERATIONS = 480000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a 256-bit key from the passphrase and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KEY_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data with integrity protection and saves it to a file.

    The file format is: salt | nonce | ciphertext + tag
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    data_bytes = data.encode('utf-8')
    ciphertext_with_tag = aesgcm.encrypt(nonce, data_bytes, None)

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext_with_tag)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieves and decrypts data, raising AccessError on failure.

    Failure can be due to an incorrect passphrase or file corruption.
    """
    try:
        with open(filepath, 'rb') as f:
            encrypted_data = f.read()
    except FileNotFoundError:
        raise AccessError(f"File not found: {filepath}")

    if len(encrypted_data) < (SALT_SIZE + NONCE_SIZE):
        raise AccessError("File is corrupted or incomplete.")

    salt = encrypted_data[:SALT_SIZE]
    nonce = encrypted_data[SALT_SIZE:SALT_SIZE + NONCE_SIZE]
    ciphertext_with_tag = encrypted_data[SALT_SIZE + NONCE_SIZE:]

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    try:
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
        return decrypted_bytes.decode('utf-8')
    except InvalidTag:
        raise AccessError("Failed to decrypt: incorrect passphrase or file has been corrupted.")

def main():
    """
    Demonstrates successful and failed file storage/retrieval operations.
    """
    TEST_FILE = "confidential_data.bin"
    CORRECT_PASSPHRASE = "super_secret_p@ssw0rd_123!"
    WRONG_PASSPHRASE = "this_is_not_the_password"
    SECRET_DATA = "The launch codes are: Red-October, Silent-Hunter, Ghost-Protocol."

    print("--- Secure Storage: Iteration 2 ---")

    try:
        # 1. Successful storage and retrieval
        print("\n[1] Demonstrating successful storage and retrieval...")
        store_file(TEST_FILE, SECRET_DATA, CORRECT_PASSPHRASE)
        print(f"File '{TEST_FILE}' stored successfully.")
        retrieved_data = retrieve_file(TEST_FILE, CORRECT_PASSPHRASE)
        print("File retrieved successfully.")
        print(f"  -> Retrieved data: '{retrieved_data}'")
        assert retrieved_data == SECRET_DATA
        print("  -> Data verification successful.")

        # 2. Failed retrieval with wrong passphrase
        print("\n[2] Demonstrating failed retrieval with wrong passphrase...")
        try:
            retrieve_file(TEST_FILE, WRONG_PASSPHRASE)
        except AccessError as e:
            print(f"Successfully caught expected error: {e}")

        # 3. Failed retrieval with corrupted file
        print("\n[3] Demonstrating failed retrieval with corrupted file...")
        # Corrupt the file by flipping a bit in the ciphertext
        with open(TEST_FILE, "r+b") as f:
            f.seek(SALT_SIZE + NONCE_SIZE + 10)  # Go 10 bytes into ciphertext
            original_byte = f.read(1)
            f.seek(-1, os.SEEK_CUR)
            # Flip the bits of the byte
            corrupted_byte = bytes([original_byte[0] ^ 0xFF])
            f.write(corrupted_byte)
        print("File has been manually corrupted.")

        try:
            retrieve_file(TEST_FILE, CORRECT_PASSPHRASE)
        except AccessError as e:
            print(f"Successfully caught expected error: {e}")

    finally:
        # Clean up the test file
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
            print(f"\nCleanup: Removed '{TEST_FILE}'.")

if __name__ == "__main__":
    main()