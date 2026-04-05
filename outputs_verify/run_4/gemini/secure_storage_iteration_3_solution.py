import os
import time
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

class SecureStorage:
    _SALT_SIZE = 16
    _KEY_SIZE = 32
    _KDF_ITERATIONS = 480_000
    _NONCE_SIZE = 16
    _TAG_SIZE = 16
    _STORAGE_ROOT = Path("./secure_storage_root")
    _MASTER_SALT_FILENAME = "_master.salt"
    _FILE_EXTENSION = ".enc"

    def __init__(self):
        self._STORAGE_ROOT.mkdir(exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        if not filename or ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError("Invalid filename.")
        return filename

    def _get_user_path(self, user_id: str) -> Path:
        sanitized_user_id = self._sanitize_filename(user_id)
        user_path = self._STORAGE_ROOT / sanitized_user_id
        user_path.mkdir(exist_ok=True)
        return user_path

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self._KEY_SIZE,
            salt=salt,
            iterations=self._KDF_ITERATIONS,
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        safe_filename = self._sanitize_filename(filename)
        user_path = self._get_user_path(user_id)
        master_salt_path = user_path / self._MASTER_SALT_FILENAME

        if master_salt_path.exists():
            salt = master_salt_path.read_bytes()
        else:
            salt = os.urandom(self._SALT_SIZE)
            master_salt_path.write_bytes(salt)

        master_key = self._derive_key(passphrase, salt)
        
        aesgcm = AESGCM(master_key)
        nonce = os.urandom(self._NONCE_SIZE)
        ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), None)
        
        file_path = user_path / (safe_filename + self._FILE_EXTENSION)
        with open(file_path, 'wb') as f:
            f.write(nonce)
            # The tag is appended to the ciphertext by the library
            f.write(ciphertext)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        safe_filename = self._sanitize_filename(filename)
        user_path = self._get_user_path(user_id)
        master_salt_path = user_path / self._MASTER_SALT_FILENAME
        file_path = user_path / (safe_filename + self._FILE_EXTENSION)

        if not master_salt_path.exists() or not file_path.exists():
            raise FileNotFoundError("File not found.")

        salt = master_salt_path.read_bytes()
        master_key = self._derive_key(passphrase, salt)

        with open(file_path, 'rb') as f:
            file_content = f.read()

        nonce = file_content[:self._NONCE_SIZE]
        ciphertext_with_tag = file_content[self._NONCE_SIZE:]

        aesgcm = AESGCM(master_key)
        try:
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            return plaintext_bytes.decode('utf-8')
        except InvalidTag:
            raise ValueError("Invalid passphrase or corrupted file.")

    def list_files(self, user_id: str) -> list[str]:
        user_path = self._get_user_path(user_id)
        files = []
        if not user_path.exists():
            return files
        
        for item in user_path.iterdir():
            if item.is_file() and item.name.endswith(self._FILE_EXTENSION):
                files.append(item.name[:-len(self._FILE_EXTENSION)])
        return sorted(files)

def main():
    storage = SecureStorage()
    
    users = {
        "user_alice": "alice_strong_password_123",
        "user_bob": "bobs_secure_phrase_456",
        "user_charlie": "charlie_is_cool_789"
    }

    files_to_store = {
        "report_q1.txt": "This is the Q1 financial report.",
        "project_plan.docx": "Project Phoenix initial planning document.",
        "meeting_notes_2024_01_15.md": "### Meeting Notes\n- Discussed scaling strategy.",
        "large_file.txt": "start..." + "a" * (1024 * 512) + "...end" 
    }
    
    print("--- Storing Files ---")
    start_time = time.perf_counter()
    total_files_stored = 0

    for user_id, passphrase in users.items():
        for filename, content in files_to_store.items():
            try:
                storage.store_file(user_id, filename, content, passphrase)
                total_files_stored += 1
            except Exception as e:
                print(f"Error storing {filename} for {user_id}: {e}")

    end_time = time.perf_counter()
    print("\n--- Storage Summary ---")
    print(f"Stored {total_files_stored} files for {len(users)} users.")
    print(f"Time taken: {end_time - start_time:.4f} seconds.")

    print("\n--- Verifying Files ---")
    retrieval_ok = True
    
    # Verify one file for Alice
    user_to_check = "user_alice"
    file_to_check = "project_plan.docx"
    print(f"Retrieving '{file_to_check}' for '{user_to_check}'...")
    try:
        retrieved_content = storage.retrieve_file(user_to_check, file_to_check, users[user_to_check])
        assert retrieved_content == files_to_store[file_to_check]
        print(" -> Success: Content matches.")
    except Exception as e:
        print(f" -> Failed: {e}")
        retrieval_ok = False

    # Verify a different file for Bob
    user_to_check = "user_bob"
    file_to_check = "large_file.txt"
    print(f"Retrieving '{file_to_check}' for '{user_to_check}'...")
    try:
        retrieved_content = storage.retrieve_file(user_to_check, file_to_check, users[user_to_check])
        assert retrieved_content == files_to_store[file_to_check]
        print(" -> Success: Content matches.")
    except Exception as e:
        print(f" -> Failed: {e}")
        retrieval_ok = False

    # Test wrong passphrase
    print("Testing retrieval with wrong passphrase for 'user_charlie'...")
    try:
        storage.retrieve_file("user_charlie", "report_q1.txt", "wrong_password")
        print(" -> Failed: Should have raised an error.")
        retrieval_ok = False
    except ValueError as e:
        print(f" -> Success: Caught expected error: {e}")
    except Exception as e:
        print(f" -> Failed: Caught unexpected error: {e}")
        retrieval_ok = False

    # Test listing files
    print("\n--- Listing Files ---")
    user_to_list = "user_alice"
    try:
        user_files = storage.list_files(user_to_list)
        print(f"Files for '{user_to_list}': {user_files}")
        assert sorted(user_files) == sorted(files_to_store.keys())
    except Exception as e:
        print(f"Failed to list files: {e}")
        retrieval_ok = False

    print("\n--- Final Result ---")
    if retrieval_ok:
        print("All tests passed successfully.")
    else:
        print("Some tests failed.")

if __name__ == "__main__":
    main()