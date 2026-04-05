import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
ITERATIONS = 480_000
KEY_SIZE = 32
NONCE_SIZE = 12

def store_file(filepath: str, data: str, passphrase: str) -> None:
    backend = default_backend()
    salt = os.urandom(SALT_SIZE)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
        backend=backend
    )
    key = kdf.derive(passphrase.encode('utf-8'))
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    backend = default_backend()

    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        ciphertext = f.read()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
        backend=backend
    )
    
    try:
        key = kdf.derive(passphrase.encode('utf-8'))
        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode('utf-8')
    except InvalidTag:
        raise ValueError("Invalid passphrase or corrupted file")

def main():
    filepath = "confidential_document.bin"
    passphrase = "super-secret-passphrase-123!"
    document_data = "Project Chimera: Q3 Financial Projections. Revenue forecast: $15M."

    print("Storing file securely...")
    store_file(filepath, document_data, passphrase)
    print(f"File '{filepath}' saved.")

    print("\nRetrieving file with correct passphrase...")
    try:
        retrieved_data = retrieve_file(filepath, passphrase)
        print("Decryption successful.")
        print("Original Data:\n---")
        print(retrieved_data)
        print("---")
        assert retrieved_data == document_data
        print("Verification successful: Retrieved data matches original data.")
    except ValueError as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"\nCleaned up file '{filepath}'.")

if __name__ == "__main__":
    main()