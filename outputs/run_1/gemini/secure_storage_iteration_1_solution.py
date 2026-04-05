import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
KEY_SIZE = 32
ITERATIONS = 480_000
NONCE_SIZE = 12

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(passphrase.encode('utf-8'))

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        ciphertext = f.read()
        
    key = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    
    try:
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_data.decode('utf-8')
    except InvalidTag:
        raise ValueError("Invalid passphrase or corrupted file")

def main():
    filepath = "confidential_document.bin"
    passphrase = "super-secret-passphrase-123"
    document = "This is a top-secret document containing sensitive corporate information."

    print(f"Storing file '{filepath}'...")
    store_file(filepath, document, passphrase)
    print("File stored successfully.")
    print("-" * 40)

    print("Attempting to retrieve with the CORRECT passphrase...")
    try:
        retrieved_document = retrieve_file(filepath, passphrase)
        print("Retrieval successful!")
        print(f"Original:    '{document}'")
        print(f"Retrieved:   '{retrieved_document}'")
        if document == retrieved_document:
            print("Verification: PASS")
        else:
            print("Verification: FAIL - Data mismatch")
    except ValueError as e:
        print(f"Error: {e}")
        print("Verification: FAIL - Exception raised")
    print("-" * 40)
    
    print("Attempting to retrieve with an INCORRECT passphrase...")
    try:
        retrieve_file(filepath, "this-is-wrong")
        print("Error: Retrieval succeeded unexpectedly.")
        print("Verification: FAIL")
    except ValueError as e:
        print(f"Retrieval failed as expected: {e}")
        print("Verification: PASS")
    print("-" * 40)

    if os.path.exists(filepath):
        os.remove(filepath)
        print(f"Cleaned up file '{filepath}'.")

if __name__ == "__main__":
    main()