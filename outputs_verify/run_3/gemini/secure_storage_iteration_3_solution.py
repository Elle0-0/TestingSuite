import os
import shutil
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE_BYTES = 32
KDF_ITERATIONS = 480_000
STORAGE_DIR = "secure_storage_root"

class SecureStorage:
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _get_user_path(self, user_id: str) -> str:
        if ".." in user_id or "/" in user_id or "\\" in user_id:
            raise ValueError("Invalid user_id.")
        path = os.path.join(self.base_path, user_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _get_file_path(self, user_id: str, filename: str) -> str:
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError("Invalid filename.")
        user_path = self._get_user_path(user_id)
        return os.path.join(user_path, f"{filename}.enc")

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE_BYTES,
            salt=salt,
            iterations=KDF_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        file_path = self._get_file_path(user_id, filename)
        salt = os.urandom(SALT_SIZE)
        key = self._derive_key(passphrase, salt)
        
        aesgcm = AESGCM(key)
        nonce = os.urandom(NONCE_SIZE)
        encrypted_data = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

        with open(file_path, 'wb') as f:
            f.write(salt)
            f.write(nonce)
            f.write(encrypted_data)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        file_path = self._get_file_path(user_id, filename)

        try:
            with open(file_path, 'rb') as f:
                salt = f.read(SALT_SIZE)
                nonce = f.read(NONCE_SIZE)
                encrypted_data = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'.")

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)

        try:
            plaintext_bytes = aesgcm.decrypt(nonce, encrypted_data, None)
            return plaintext_bytes.decode('utf-8')
        except InvalidTag:
            raise ValueError("Invalid passphrase or file has been tampered with.")

    def list_files(self, user_id: str) -> list[str]:
        user_path = self._get_user_path(user_id)
        if not os.path.isdir(user_path):
            return []
        
        files = [f[:-4] for f in os.listdir(user_path) if f.endswith(".enc")]
        return sorted(files)

def main():
    if os.path.exists(STORAGE_DIR):
        shutil.rmtree(STORAGE_DIR)
        
    storage = SecureStorage(STORAGE_DIR)
    users = {
        "user_alice": "alice_pass_123",
        "user_bob": "bob_secret_456",
        "user_charlie": "charlie_key_789"
    }
    num_files_per_user = 50
    file_count = 0
    start_time = time.time()

    print("Storing files...")
    for i in range(num_files_per_user):
        for user_id, passphrase in users.items():
            filename = f"document_{i+1}.txt"
            data = f"This is secret content for {user_id} in file {filename}."
            storage.store_file(user_id, filename, data, passphrase)
            file_count += 1

    print("Verifying stored files...")
    for user_id, passphrase in users.items():
        files = storage.list_files(user_id)
        assert len(files) == num_files_per_user
        
        file_to_check = "document_11.txt"
        retrieved_data = storage.retrieve_file(user_id, file_to_check, passphrase)
        original_data = f"This is secret content for {user_id} in file {file_to_check}."
        assert retrieved_data == original_data
    
    print("Testing failure cases...")
    try:
        storage.retrieve_file("user_alice", "document_1.txt", "wrong_password")
    except ValueError as e:
        print(f"Successfully caught expected error: {e}")

    try:
        storage.retrieve_file("user_alice", "non_existent_file.txt", "alice_pass_123")
    except FileNotFoundError as e:
        print(f"Successfully caught expected error: {e}")

    end_time = time.time()
    
    print("\n--- Summary ---")
    print(f"Total files stored: {file_count}")
    print(f"Total time taken: {end_time - start_time:.4f} seconds")
    
    shutil.rmtree(STORAGE_DIR)
    print(f"Cleaned up storage directory: {STORAGE_DIR}")


if __name__ == "__main__":
    main()