import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

# --- Constants for cryptographic operations ---
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32  # For AES-256
PBKDF2_ITERATIONS = 480000


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data using a passphrase and stores it in a file.

    The file format is: [salt][nonce][encrypted_data_with_tag]
    """
    salt = os.urandom(SALT_SIZE)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend()
    )
    key = kdf.derive(passphrase.encode('utf-8'))

    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    data_bytes = data.encode('utf-8')
    encrypted_data = aesgcm.encrypt(nonce, data_bytes, None)

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(encrypted_data)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Reads an encrypted file, decrypts it with a passphrase, and returns the data.

    Raises:
        cryptography.exceptions.InvalidTag: If the passphrase is incorrect or the
                                            data has been tampered with.
        FileNotFoundError: If the filepath does not exist.
    """
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        encrypted_data = f.read()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend()
    )
    key = kdf.derive(passphrase.encode('utf-8'))

    aesgcm = AESGCM(key)
    
    decrypted_data_bytes = aesgcm.decrypt(nonce, encrypted_data, None)
    
    return decrypted_data_bytes.decode('utf-8')


def main():
    """
    Demonstrates the store_file and retrieve_file functionality.
    """
    filepath = "confidential_document.bin"
    secret_passphrase = "super-secret-password-123"
    wrong_passphrase = "this-is-not-the-password"
    document_content = "This is a top secret document containing sensitive corporate data."

    # 1. Store the file securely
    print(f"Storing file '{filepath}'...")
    store_file(filepath, document_content, secret_passphrase)
    print("File stored securely.")
    print("-" * 30)

    # 2. Retrieve the file with the correct passphrase
    print("Attempting to retrieve file with the correct passphrase...")
    try:
        retrieved_content = retrieve_file(filepath, secret_passphrase)
        print("File retrieved successfully.")
        print(f"Retrieved content: '{retrieved_content}'")
        assert document_content == retrieved_content
        print("Verification successful: Content matches original document.")
    except Exception as e:
        print(f"An unexpected error occurred during retrieval: {e}")
    print("-" * 30)

    # 3. Attempt to retrieve the file with the wrong passphrase
    print("Attempting to retrieve file with an incorrect passphrase...")
    try:
        retrieve_file(filepath, wrong_passphrase)
        # This line should not be reached
        print("Error: File was retrieved with the wrong passphrase!")
    except InvalidTag:
        print("Success: Decryption failed with the wrong passphrase, as expected.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    print("-" * 30)

    # Clean up the created file
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"Cleaned up file: '{filepath}'")

if __name__ == "__main__":
    main()