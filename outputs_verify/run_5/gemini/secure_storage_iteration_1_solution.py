import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
KEY_SIZE = 32  # For AES-256
ITERATIONS = 480_000
NONCE_SIZE = 12

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data using a passphrase and stores it in a file.

    The file format is: salt (16 bytes) + nonce (12 bytes) + ciphertext (variable)
    AES-256-GCM is used for authenticated encryption.
    PBKDF2-HMAC-SHA256 is used to derive the key from the passphrase.
    """
    salt = os.urandom(SALT_SIZE)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
    )
    key = kdf.derive(passphrase.encode('utf-8'))

    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    # Encrypt the data. The authentication tag is automatically appended.
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Retrieves and decrypts data from a file using a passphrase.

    Raises cryptography.exceptions.InvalidTag if the passphrase is incorrect
    or the file has been tampered with.
    """
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        ciphertext_with_tag = f.read()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
    )
    key = kdf.derive(passphrase.encode('utf-8'))

    aesgcm = AESGCM(key)
    
    # Decrypt the data. This will raise InvalidTag on failure.
    decrypted_data = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    
    return decrypted_data.decode('utf-8')

def main():
    """
    Demonstrates storing and retrieving a confidential document.
    """
    filepath = "confidential_document.bin"
    correct_passphrase = "super-secret-passphrase-123"
    wrong_passphrase = "this-is-the-wrong-passphrase"
    document_content = ("This is a highly confidential document.\n"
                        "Project: Chimera\n"
                        "Status: Active\n"
                        "Details: All agents must report to Site-B by 0400.")

    # --- Store the file securely ---
    try:
        store_file(filepath, document_content, correct_passphrase)
        print(f"Successfully stored confidential data to '{filepath}'.")
    except Exception as e:
        print(f"Error during file storage: {e}")
        return

    # --- Retrieve the file with the correct passphrase ---
    print("\nAttempting retrieval with the CORRECT passphrase...")
    try:
        retrieved_content = retrieve_file(filepath, correct_passphrase)
        print("Success! Decrypted content matches original content:")
        print("-" * 20)
        print(retrieved_content)
        print("-" * 20)
        assert retrieved_content == document_content
    except InvalidTag:
        print("Decryption failed! The passphrase may be incorrect or the file is corrupt.")
    except Exception as e:
        print(f"An unexpected error occurred during retrieval: {e}")

    # --- Attempt to retrieve with the wrong passphrase ---
    print("\nAttempting retrieval with the WRONG passphrase...")
    try:
        retrieve_file(filepath, wrong_passphrase)
        # This line should not be reached
        print("Error: Decryption succeeded with the wrong passphrase!")
    except InvalidTag:
        print("Success! Decryption failed as expected with the wrong passphrase.")
    except Exception as e:
        print(f"An unexpected error occurred during failed retrieval attempt: {e}")

    # --- Clean up the created file ---
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"\nCleaned up file: '{filepath}'")

if __name__ == "__main__":
    main()