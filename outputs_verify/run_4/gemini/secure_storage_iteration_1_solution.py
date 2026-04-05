import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
KDF_ITERATIONS = 480000

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a 32-byte key from a passphrase and salt using PBKDF2-HMAC-SHA256."""
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
    Encrypts data using AES-GCM with a key derived from the passphrase and saves it.
    The file format is: salt (16 bytes) | nonce (12 bytes) | encrypted_data_with_tag
    """
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    encrypted_data = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(encrypted_data)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Reads an encrypted file, decrypts it, and returns the original data.
    
    Raises:
        FileNotFoundError: If the filepath does not exist.
        InvalidTag: If the passphrase is incorrect or the file has been tampered with.
    """
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        encrypted_data = f.read()

    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    
    decrypted_bytes = aesgcm.decrypt(nonce, encrypted_data, None)
    return decrypted_bytes.decode('utf-8')

def main():
    """
    Demonstrates storing a file, retrieving it with the correct passphrase,
    and failing to retrieve it with an incorrect passphrase.
    """
    filepath = "confidential_document.bin"
    passphrase = "super-secret-passphrase-for-secure-storage-123!"
    document_data = "Meeting Notes - Project Chimera\n\n- Phase 1 budget approved.\n- Security protocol VX-7 is now active.\n- Do not discuss outside this group."

    print(f"1. Storing confidential data to '{filepath}'...")
    store_file(filepath, document_data, passphrase)
    print("   File stored and encrypted successfully.")
    print("-" * 40)

    print("2. Retrieving data with the CORRECT passphrase...")
    try:
        retrieved_data = retrieve_file(filepath, passphrase)
        print("   Retrieval successful. Contents:")
        print("   " + "-"*30)
        print(f"   {retrieved_data.replace('\n', '\n   ')}")
        print("   " + "-"*30)
        assert document_data == retrieved_data
        print("\n   Verification complete: Original and retrieved data match.")
    except Exception as e:
        print(f"   An unexpected error occurred: {e}")
    print("-" * 40)
    
    print("3. Attempting to retrieve data with an INCORRECT passphrase...")
    wrong_passphrase = "this is not the correct password"
    try:
        retrieve_file(filepath, wrong_passphrase)
    except InvalidTag:
        print("   Success: The system correctly rejected the incorrect passphrase.")
    except Exception as e:
        print(f"   An unexpected error occurred: {e}")
    
    # Clean up the temporary file
    if os.path.exists(filepath):
        os.remove(filepath)

if __name__ == "__main__":
    main()