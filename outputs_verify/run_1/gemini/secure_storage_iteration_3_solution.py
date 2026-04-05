import os
import secrets
import time
import shutil
import tempfile
from typing import List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

class SecureStorage:
    _SCRYPT_N = 2**14
    _SCRYPT_R = 8
    _SCRYPT_P = 1
    _SCRYPT_LEN = 32
    _AES_KEY_SIZE = 32
    _GCM_NONCE_SIZE = 12
    _GCM_TAG_SIZE = 16

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    def _get_user_path(self, user_id: str) -> str:
        if not user_id or os.path.sep in user_id or '..' in user_id:
            raise ValueError("Invalid user_id")
        return os.path.join(self.storage_path, user_id)

    def _get_file_path(self, user_id: str, filename: str) -> str:
        clean_filename = os.path.basename(filename)
        if not filename or filename != clean_filename:
            raise ValueError("Invalid filename. It must not contain path separators.")
        user_path = self._get_user_path(user_id)
        return os.path.join(user_path, filename)

    def _derive_master_key(self, passphrase: str, user_id_as_salt: str) -> bytes:
        kdf = Scrypt(
            salt=user_id_as_salt.encode('utf-8'),
            length=self._SCRYPT_LEN,
            n=self._SCRYPT_N,
            r=self._SCRYPT_R,
            p=self._SCRYPT_P,
            backend=default_backend()
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        file_path = self._get_file_path(user_id, filename)
        user_path = os.path.dirname(file_path)
        os.makedirs(user_path, exist_ok=True)

        data_bytes = data.encode('utf-8')

        master_key = self._derive_master_key(passphrase, user_id)
        master_key_aead = AESGCM(master_key)

        file_encryption_key = secrets.token_bytes(self._AES_KEY_SIZE)

        nonce_fek = secrets.token_bytes(self._GCM_NONCE_SIZE)
        wrapped_fek_with_tag = master_key_aead.encrypt(nonce_fek, file_encryption_key, None)

        data_aead = AESGCM(file_encryption_key)
        nonce_data = secrets.token_bytes(self._GCM_NONCE_SIZE)
        encrypted_data_with_tag = data_aead.encrypt(nonce_data, data_bytes, None)

        with open(file_path, 'wb') as f:
            f.write(nonce_fek)
            f.write(wrapped_fek_with_tag)
            f.write(nonce_data)
            f.write(encrypted_data_with_tag)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        file_path = self._get_file_path(user_id, filename)
        
        try:
            with open(file_path, 'rb') as f:
                nonce_fek = f.read(self._GCM_NONCE_SIZE)
                wrapped_fek_len = self._AES_KEY_SIZE + self._GCM_TAG_SIZE
                wrapped_fek_with_tag = f.read(wrapped_fek_len)
                nonce_data = f.read(self._GCM_NONCE_SIZE)
                encrypted_data_with_tag = f.read()

            master_key = self._derive_master_key(passphrase, user_id)
            master_key_aead = AESGCM(master_key)
            
            file_encryption_key = master_key_aead.decrypt(nonce_fek, wrapped_fek_with_tag, None)

            data_aead = AESGCM(file_encryption_key)
            decrypted_data_bytes = data_aead.decrypt(nonce_data, encrypted_data_with_tag, None)

            return decrypted_data_bytes.decode('utf-8')
        except (FileNotFoundError, ValueError, InvalidTag):
            raise ValueError("Failed to retrieve file: invalid passphrase, file not found, or corrupted file.")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred during file retrieval: {e}")

    def list_files(self, user_id: str) -> List[str]:
        try:
            user_path = self._get_user_path(user_id)
            if not os.path.isdir(user_path):
                return []
            return sorted([
                f for f in os.listdir(user_path)
                if os.path.isfile(os.path.join(user_path, f))
            ])
        except (ValueError, OSError):
            return []

def main():
    temp_dir = tempfile.mkdtemp()
    storage = SecureStorage(temp_dir)

    users = {
        "alice-42": "alice_pass_123",
        "bob-99": "bob_secret_phrase",
        "charlie-07": "42-is-the-answer"
    }

    files_to_store = {
        "alice-42": [("report.txt", "This is the Q3 financial report."),
                     ("notes.txt", "Meeting notes: remember to follow up with Bob.")],
        "bob-99": [("project_plan.docx", "Phase 1: ... Phase 2: ..."),
                   ("large_data.csv", "id,value\n" * 50000)],
        "charlie-07": []
    }

    total_files_stored = 0
    start_time = time.perf_counter()

    for user_id, passphrase in users.items():
        for filename, data in files_to_store.get(user_id, []):
            storage.store_file(user_id, filename, data, passphrase)
            total_files_stored += 1

    end_time = time.perf_counter()
    time_taken = end_time - start_time

    # Verification
    # 1. List and retrieve for alice
    alice_files = storage.list_files("alice-42")
    assert alice_files == ["notes.txt", "report.txt"]
    retrieved_notes = storage.retrieve_file("alice-42", "notes.txt", users["alice-42"])
    assert retrieved_notes == files_to_store["alice-42"][1][1]

    # 2. Check bob's large file
    retrieved_large_data = storage.retrieve_file("bob-99", "large_data.csv", users["bob-99"])
    assert retrieved_large_data == files_to_store["bob-99"][1][1]

    # 3. Check charlie (no files)
    assert storage.list_files("charlie-07") == []

    # 4. Check wrong passphrase
    try:
        storage.retrieve_file("alice-42", "report.txt", "wrong_password")
        assert False, "Should have failed with wrong passphrase"
    except ValueError:
        pass  # Expected

    # 5. Check non-existent file
    try:
        storage.retrieve_file("bob-99", "non_existent.txt", users["bob-99"])
        assert False, "Should have failed for non-existent file"
    except ValueError:
        pass  # Expected

    # 6. Check non-existent user
    assert storage.list_files("dave-123") == []
    
    print("--- Secure Storage Summary ---")
    print(f"Total files stored: {total_files_stored}")
    print(f"Total time taken: {time_taken:.4f} seconds")

    shutil.rmtree(temp_dir)