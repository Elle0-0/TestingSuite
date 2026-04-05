import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
KDF_ITERATIONS = 480000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    backend = default_backend()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=backend
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    data_bytes = data.encode('utf-8')
    encrypted_data = aesgcm.encrypt(nonce, data_bytes, None)
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(encrypted_data)

def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        encrypted_data = f.read()

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    
    try:
        decrypted_data_bytes = aesgcm.decrypt(nonce, encrypted_data, None)
        return decrypted_data_bytes.decode('utf-8')
    except InvalidTag:
        raise ValueError("Invalid passphrase or file is corrupted.")

def main():
    filepath = "confidential_document.bin"
    passphrase = "super_secret_password_123!"
    original_data = "This is a top-secret document containing sensitive corporate information."

    print(f"Original data: {original_data}\n")

    # Store the file
    store_file(filepath, original_data, passphrase)
    print(f"Data stored securely in '{filepath}'.")

    # Retrieve with the correct passphrase
    try:
        retrieved_data = retrieve_file(filepath, passphrase)
        print("\nRetrieving with correct passphrase...")
        print(f"Retrieved data: {retrieved_data}")
        assert original_data == retrieved_data
        print("Verification successful: Original and retrieved data match.")
    except ValueError as e:
        print(f"An error occurred: {e}")

    # Attempt to retrieve with the wrong passphrase
    try:
        print("\nAttempting to retrieve with incorrect passphrase...")
        retrieve_file(filepath, "wrong_password")
    except ValueError as e:
        print(f"Successfully caught expected error: {e}")
    finally:
        # Clean up the created file
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"\nCleaned up file: '{filepath}'")

if __name__ == "__main__":
    main()