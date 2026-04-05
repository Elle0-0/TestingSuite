import os
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from typing import Final

# Cryptographic constants
SALT_SIZE: Final[int] = 16
KEY_BYTES: Final[int] = 32  # AES-256
PBKDF2_ITERATIONS: Final[int] = 100000
GCM_TAG_SIZE: Final[int] = 16
GCM_NONCE_SIZE: Final[int] = 16


def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data using a passphrase and stores it in a file.
    The file format is: salt | nonce | tag | ciphertext
    """
    salt = get_random_bytes(SALT_SIZE)
    key = PBKDF2(passphrase.encode('utf-8'), salt, dkLen=KEY_BYTES, count=PBKDF2_ITERATIONS)

    cipher = AES.new(key, AES.MODE_GCM)
    # The nonce is generated automatically by the library here
    
    ciphertext, tag = cipher.encrypt_and_digest(data.encode('utf-8'))

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(cipher.nonce)
        f.write(tag)
        f.write(ciphertext)


def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Reads an encrypted file, decrypts it with a passphrase, and returns the data.
    Raises ValueError on incorrect passphrase or tampered file.
    """
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(GCM_NONCE_SIZE)
        tag = f.read(GCM_TAG_SIZE)
        ciphertext = f.read()

    key = PBKDF2(passphrase.encode('utf-8'), salt, dkLen=KEY_BYTES, count=PBKDF2_ITERATIONS)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    
    decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
    
    return decrypted_data.decode('utf-8')


def main():
    """
    Demonstrates the store and retrieve functionality.
    """
    filepath = "confidential_document.dat"
    passphrase = "s3cure_p@ssphr@se_f0r_t3st!ng"
    original_data = "This is a top-secret document. The meeting is at midnight."

    # --- Store the file ---
    print("--- Secure Storage: First Iteration ---")
    store_file(filepath, original_data, passphrase)
    print(f"File '{filepath}' has been encrypted and stored.")
    print("-" * 40)

    # --- Retrieve with the correct passphrase ---
    print("Attempting to retrieve with the CORRECT passphrase...")
    try:
        retrieved_data = retrieve_file(filepath, passphrase)
        print("Success: File decrypted.")
        print(f"Retrieved content: '{retrieved_data}'")
        assert original_data == retrieved_data
        print("Verification: Original and retrieved data match.")
    except Exception as e:
        print(f"Error: An unexpected error occurred during retrieval. {e}")
    print("-" * 40)

    # --- Attempt to retrieve with an incorrect passphrase ---
    print("Attempting to retrieve with an INCORRECT passphrase...")
    wrong_passphrase = "wrong_password_123"
    try:
        retrieve_file(filepath, wrong_passphrase)
        print("Security Failure: File was accessible with an incorrect passphrase.")
    except ValueError:
        print("Success: Decryption failed as expected. The file remains confidential.")
    except Exception as e:
        print(f"Error: An unexpected error occurred. {e}")
    print("-" * 40)

    # --- Clean up the created file ---
    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"Cleanup: Removed temporary file '{filepath}'.")


if __name__ == "__main__":
    main()