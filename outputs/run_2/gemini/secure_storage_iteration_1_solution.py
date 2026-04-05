import os
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

SALT_SIZE = 16
ITERATIONS = 480_000
KEY_LENGTH = 32
HASH_ALGORITHM = hashes.SHA256()

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=HASH_ALGORITHM,
        length=KEY_LENGTH,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode('utf-8')))
    return key

def store_file(filepath: str, data: str, passphrase: str) -> None:
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(passphrase, salt)
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data.encode('utf-8'))
    
    with open(filepath, 'wb') as f:
        f.write(salt)
        f.write(encrypted_data)

def retrieve_file(filepath: str, passphrase: str) -> str:
    with open(filepath, 'rb') as f:
        salt = f.read(SALT_SIZE)
        encrypted_data = f.read()

    key = _derive_key(passphrase, salt)
    fernet = Fernet(key)
    
    decrypted_data_bytes = fernet.decrypt(encrypted_data)
    return decrypted_data_bytes.decode('utf-8')

def main():
    filepath = "confidential_document.dat"
    correct_passphrase = "super_secret_password_123"
    wrong_passphrase = "this_is_not_the_password"
    document_content = "This is a top secret document.\nProject Chimera is a go."

    # 1. Store the file
    store_file(filepath, document_content, correct_passphrase)

    # 2. Retrieve with correct passphrase and print to verify
    try:
        retrieved_content = retrieve_file(filepath, correct_passphrase)
        if retrieved_content == document_content:
            print("--- Verification with correct passphrase ---")
            print("SUCCESS: Retrieved content matches original content.")
            print("\nOriginal Content:\n" + "="*16)
            print(document_content)
            print("\nRetrieved Content:\n" + "="*17)
            print(retrieved_content)
        else:
            print("FAILURE: Retrieved content does not match original content.")
    except Exception as e:
        print(f"An unexpected error occurred during retrieval: {e}")

    print("\n--- Verification with incorrect passphrase ---")
    # 3. Attempt to retrieve with incorrect passphrase to verify security
    try:
        retrieve_file(filepath, wrong_passphrase)
        print("FAILURE: File was accessible with an incorrect passphrase.")
    except InvalidToken:
        print("SUCCESS: Access was denied with an incorrect passphrase, as expected.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    # 4. Clean up the created file
    if os.path.exists(filepath):
        os.remove(filepath)

if __name__ == "__main__":
    main()