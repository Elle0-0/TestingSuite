import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
PBKDF2_ITERATIONS = 390_000

def store_file(filepath: str, data: str, passphrase: str) -> None:
    """
    Encrypts data using a passphrase and saves it to a file.

    The file format is: salt | nonce | ciphertext_and_tag
    """
    backend = default_backend()
    salt = os.urandom(SALT_SIZE)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=backend
    )
    key = kdf.derive(passphrase.encode('utf-8'))

    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    
    encoded_data = data.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, encoded_data, None)

    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

def retrieve_file(filepath: str, passphrase: str) -> str:
    """
    Reads an encrypted file, decrypts it with a passphrase, and returns the data.
    """
    backend = default_backend()

    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        nonce = f.read(NONCE_SIZE)
        ciphertext = f.read()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=backend
    )
    key = kdf.derive(passphrase.encode('utf-8'))
    
    aesgcm = AESGCM(key)

    try:
        decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_data.decode('utf-8')
    except InvalidTag:
        raise ValueError("Incorrect passphrase or corrupted file.")

def main():
    """
    Demonstrates storing and retrieving a confidential document.
    """
    filepath = "confidential_document.bin"
    passphrase = "super-secret-passphrase-123"
    document_content = "This is a highly confidential document. Top secret plans inside."

    # Store the encrypted file
    store_file(filepath, document_content, passphrase)

    # Retrieve the file with the correct passphrase and print its content
    retrieved_content = retrieve_file(filepath, passphrase)
    
    print(retrieved_content)
    
    # Verify correctness (optional, for self-checking)
    assert document_content == retrieved_content

    # Clean up the created file
    os.remove(filepath)

if __name__ == "__main__":
    main()