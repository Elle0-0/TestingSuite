import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
PBKDF2_ITERATIONS = 480_000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a cryptographic key from a passphrase and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data using a passphrase and saves it to a file.

    The file format is: salt (16 bytes) + nonce (12 bytes) + ciphertext.
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

    with open(filepath, 'wb') as f:
        f.write(salt + nonce + ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Decrypts a file using a passphrase and returns the original data.
    
    Raises:
        ValueError: If the passphrase is incorrect or the file is corrupted.
    """
    with open(filepath, 'rb') as f:
        encrypted_data = f.read()

    salt = encrypted_data[:SALT_SIZE]
    nonce = encrypted_data[SALT_SIZE:SALT_SIZE + NONCE_SIZE]
    ciphertext = encrypted_data[SALT_SIZE + NONCE_SIZE:]

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    try:
        decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode('utf-8')
    except InvalidTag:
        raise ValueError("Invalid passphrase or corrupted file")

def main():
    """
    Demonstrates the secure storage and retrieval process.
    """
    filepath = "confidential_document.bin"
    passphrase = "squeamish ossifrage"
    original_data = "This is a highly confidential document. The launch codes are 000-000-007."

    try:
        # 1. Store the file securely
        store_file(filepath, original_data, passphrase)
        print(f"File '{filepath}' stored successfully.")

        # 2. Retrieve the file with the correct passphrase
        print("\nRetrieving with CORRECT passphrase...")
        retrieved_data = retrieve_file(filepath, passphrase)
        print(f"Retrieved data: {retrieved_data}")
        
        # 3. Verify correctness
        if retrieved_data == original_data:
            print("Verification successful: Retrieved data matches original data.")
        else:
            print("Verification FAILED: Data does not match.")

        # 4. Attempt to retrieve with an incorrect passphrase
        print("\nAttempting to retrieve with INCORRECT passphrase...")
        try:
            retrieve_file(filepath, "wrong passphrase")
        except ValueError as e:
            print(f"Successfully caught expected error: {e}")

    finally:
        # 5. Clean up the created file
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"\nCleaned up file '{filepath}'.")

if __name__ == "__main__":
    main()