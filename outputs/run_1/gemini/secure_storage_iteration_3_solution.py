import os
import time
import shutil
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

class SecureStorage:
    _SALT_SIZE = 16
    _KEY_SIZE = 32
    _NONCE_SIZE = 12
    _SCRYPT_N = 2**14
    _SCRYPT_R = 8
    _SCRYPT_P = 1
    _STORAGE_ROOT = "secure_storage_data_v3"

    def __init__(self):
        os.makedirs(self._STORAGE_ROOT, exist_ok=True)

    def _get_user_dir(self, user_id: str) -> str:
        safe_user_id = "".join(c for c in user_id if c.isalnum() or c in ('-', '_'))
        return os.path.join(self._STORAGE_ROOT, safe_user_id)

    def _get_file_path(self, user_id: str, filename: str) -> str:
        user_dir = self._get_user_dir(user_id)
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.'))
        return os.path.join(user_dir, safe_filename)

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = Scrypt(
            salt=salt,
            length=self._KEY_SIZE,
            n=self._SCRYPT_N,
            r=self._SCRYPT_R,
            p=self._SCRYPT_P,
            backend=default_backend()
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._get_user_dir(user_id)
        os.makedirs(user_dir, exist_ok=True)
        file_path = self._get_file_path(user_id, filename)

        salt = os.urandom(self._SALT_SIZE)
        key = self._derive_key(passphrase, salt)
        
        aesgcm = AESGCM(key)
        nonce = os.urandom(self._NONCE_SIZE)
        
        ciphertext_and_tag = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

        with open(file_path, 'wb') as f:
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext_and_tag)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        file_path = self._get_file_path(user_id, filename)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'")

        with open(file_path, 'rb') as f:
            salt = f.read(self._SALT_SIZE)
            nonce = f.read(self._NONCE_SIZE)
            ciphertext_and_tag = f.read()

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)

        try:
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_and_tag, None)
            return plaintext_bytes.decode('utf-8')
        except InvalidTag:
            raise ValueError("Invalid passphrase or file has been tampered with.")

    def list_files(self, user_id: str) -> list[str]:
        user_dir = self._get_user_dir(user_id)
        if not os.path.isdir(user_dir):
            return []
        return os.listdir(user_dir)

def main():
    storage = SecureStorage()
    files_stored_count = 0
    
    users = {
        "alice": "alice_strong_password_123",
        "bob": "bob_secure_phrase_456"
    }
    
    files_to_store = {
        "report.txt": "This is the confidential annual report.",
        "project_plan.docx": "Q3 Project Plan: Operation Dragonfly.",
        "notes_2024.md": "# Meeting Notes\n- Discussed scaling issues\n- Agreed on new crypto protocol"
    }

    print("--- Starting Secure Storage Test ---")
    start_time = time.perf_counter()

    # --- Store files for multiple users ---
    print("\n--- Storing Files ---")
    for user_id, passphrase in users.items():
        print(f"Storing files for user: {user_id}")
        for filename, content in files_to_store.items():
            try:
                storage.store_file(user_id, filename, content, passphrase)
                files_stored_count += 1
                print(f"  - Stored '{filename}'")
            except Exception as e:
                print(f"  - FAILED to store '{filename}': {e}")
    
    # --- List and retrieve files ---
    print("\n--- Retrieving and Verifying Files ---")
    for user_id, passphrase in users.items():
        print(f"Verifying files for user: {user_id}")
        try:
            file_list = storage.list_files(user_id)
            print(f"  - Found files: {file_list}")
            assert len(file_list) == len(files_to_store)

            for filename in file_list:
                original_content = files_to_store[filename]
                retrieved_content = storage.retrieve_file(user_id, filename, passphrase)
                assert original_content == retrieved_content
                print(f"  - Successfully retrieved and verified '{filename}'")
        except Exception as e:
            print(f"  - FAILED verification for user '{user_id}': {e}")

    # --- Test failure cases ---
    print("\n--- Testing Failure Cases ---")
    
    # 1. Wrong passphrase
    try:
        print("Attempting to retrieve 'report.txt' for 'alice' with wrong passphrase...")
        storage.retrieve_file("alice", "report.txt", "wrong_password")
    except ValueError as e:
        print(f"  - SUCCESS: Caught expected error: {e}")
    
    # 2. Non-existent file
    try:
        print("Attempting to retrieve non-existent file 'ghost.txt' for 'bob'...")
        storage.retrieve_file("bob", "ghost.txt", users["bob"])
    except FileNotFoundError as e:
        print(f"  - SUCCESS: Caught expected error: {e}")

    # 3. Non-existent user
    print("Attempting to list files for non-existent user 'charlie'...")
    files = storage.list_files("charlie")
    assert files == []
    print(f"  - SUCCESS: Received empty list for non-existent user: {files}")

    end_time = time.perf_counter()
    duration = end_time - start_time
    
    print("\n--- Test Summary ---")
    print(f"Total files stored and verified: {files_stored_count}")
    print(f"Total time taken: {duration:.4f} seconds")

    # --- Cleanup ---
    try:
        shutil.rmtree(storage._STORAGE_ROOT)
        print(f"\nCleaned up storage directory: {storage._STORAGE_ROOT}")
    except Exception as e:
        print(f"Could not clean up storage directory: {e}")

if __name__ == "__main__":
    main()