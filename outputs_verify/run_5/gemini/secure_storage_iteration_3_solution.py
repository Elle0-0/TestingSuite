import os
import json
import time
import uuid
import base64
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

KDF_SALT_SIZE = 16
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 32
AES_NONCE_SIZE = 12
AES_TAG_SIZE = 16

class SecureStorage:
    """
    Manages secure, scalable storage of files for multiple users.
    """
    def __init__(self, storage_root: str = "storage"):
        self.root_path = Path(storage_root).resolve()
        os.makedirs(self.root_path, exist_ok=True)

    def _get_user_paths(self, user_id: str) -> Tuple[Path, Path, Path]:
        user_dir = self.root_path / user_id
        meta_path = user_dir / "metadata.json"
        files_dir = user_dir / "files"
        return user_dir, meta_path, files_dir

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        kdf = Scrypt(
            salt=salt,
            length=KEY_LENGTH,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            backend=default_backend()
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def _get_or_create_metadata(self, user_id: str, passphrase: str) -> Tuple[bytes, Dict[str, Any]]:
        user_dir, meta_path, files_dir = self._get_user_paths(user_id)
        os.makedirs(files_dir, exist_ok=True)

        if not meta_path.exists():
            kdf_salt = os.urandom(KDF_SALT_SIZE)
            user_key = self._derive_key(passphrase, kdf_salt)
            
            master_key = AESGCM.generate_key(bit_length=256)
            aesgcm = AESGCM(user_key)
            master_key_nonce = os.urandom(AES_NONCE_SIZE)
            encrypted_master_key = aesgcm.encrypt(master_key_nonce, master_key, None)
            
            metadata = {
                "kdf_salt": base64.b64encode(kdf_salt).decode('utf-8'),
                "encrypted_master_key": base64.b64encode(encrypted_master_key).decode('utf-8'),
                "master_key_nonce": base64.b64encode(master_key_nonce).decode('utf-8'),
                "files": {}
            }
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return master_key, metadata

        with open(meta_path, 'r') as f:
            metadata = json.load(f)

        kdf_salt = base64.b64decode(metadata['kdf_salt'])
        user_key = self._derive_key(passphrase, kdf_salt)

        aesgcm = AESGCM(user_key)
        master_key_nonce = base64.b64decode(metadata['master_key_nonce'])
        encrypted_master_key = base64.b64decode(metadata['encrypted_master_key'])
        
        try:
            master_key = aesgcm.decrypt(master_key_nonce, encrypted_master_key, None)
            return master_key, metadata
        except InvalidTag:
            raise ValueError("Invalid passphrase or corrupted metadata.")

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir, meta_path, files_dir = self._get_user_paths(user_id)
        master_key, metadata = self._get_or_create_metadata(user_id, passphrase)

        # 1. Encrypt file data
        file_key = AESGCM.generate_key(bit_length=256)
        data_aesgcm = AESGCM(file_key)
        data_nonce = os.urandom(AES_NONCE_SIZE)
        encrypted_data = data_aesgcm.encrypt(data_nonce, data.encode('utf-8'), None)

        # 2. Encrypt the file key with the master key
        master_aesgcm = AESGCM(master_key)
        fk_nonce = os.urandom(AES_NONCE_SIZE)
        encrypted_file_key = master_aesgcm.encrypt(fk_nonce, file_key, None)

        # 3. Store encrypted data blob
        file_id = str(uuid.uuid4())
        file_path = files_dir / file_id
        with open(file_path, 'wb') as f:
            f.write(data_nonce + encrypted_data)

        # 4. Update and save metadata
        metadata['files'][filename] = {
            "file_id": file_id,
            "encrypted_file_key": base64.b64encode(encrypted_file_key).decode('utf-8'),
            "efk_nonce": base64.b64encode(fk_nonce).decode('utf-8'),
        }

        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        master_key, metadata = self._get_or_create_metadata(user_id, passphrase)

        file_info = metadata['files'].get(filename)
        if not file_info:
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'.")

        # 1. Decrypt file key
        master_aesgcm = AESGCM(master_key)
        efk_nonce = base64.b64decode(file_info['efk_nonce'])
        encrypted_file_key = base64.b64decode(file_info['encrypted_file_key'])
        
        try:
            file_key = master_aesgcm.decrypt(efk_nonce, encrypted_file_key, None)
        except InvalidTag:
            raise ValueError("Failed to decrypt file key; metadata might be corrupt.")

        # 2. Read and decrypt file data
        _, _, files_dir = self._get_user_paths(user_id)
        file_path = files_dir / file_info['file_id']
        
        if not file_path.exists():
            raise FileNotFoundError("Physical file is missing, though metadata exists.")
            
        with open(file_path, 'rb') as f:
            blob = f.read()

        data_nonce = blob[:AES_NONCE_SIZE]
        encrypted_data = blob[AES_NONCE_SIZE:]
        
        data_aesgcm = AESGCM(file_key)
        try:
            decrypted_data = data_aesgcm.decrypt(data_nonce, encrypted_data, None)
            return decrypted_data.decode('utf-8')
        except InvalidTag:
            raise ValueError("File is corrupted or has been tampered with.")

    def list_files(self, user_id: str) -> List[str]:
        _, meta_path, _ = self._get_user_paths(user_id)
        if not meta_path.exists():
            return []
        
        with open(meta_path, 'r') as f:
            metadata = json.load(f)
        
        return list(metadata.get("files", {}).keys())


def main():
    storage_root = "secure_storage_demo"
    if os.path.exists(storage_root):
        shutil.rmtree(storage_root)

    storage = SecureStorage(storage_root=storage_root)
    total_files_stored = 0
    start_time = time.time()

    users_data = {
        "user_alice": {
            "passphrase": "alice_strong_password_123",
            "files": {
                "notes.txt": "This is a secret note.",
                "project_plan.docx": "Step 1: ..., Step 2: ...",
                "large_log.log": "log entry " * 100000,
            }
        },
        "user_bob": {
            "passphrase": "bob_secure_phrase_456",
            "files": {
                "shopping_list.txt": "Milk, Bread, Eggs",
                "vacation_ideas.md": "- Hawaii\n- Japan\n- Italy",
            }
        }
    }

    print("--- Storing Files ---")
    for user_id, data in users_data.items():
        print(f"Storing files for {user_id}...")
        for filename, content in data["files"].items():
            storage.store_file(user_id, filename, content, data["passphrase"])
            total_files_stored += 1
            print(f"  Stored '{filename}'")
    
    end_time = time.time()
    duration = end_time - start_time

    print("\n--- Listing and Retrieving Files ---")
    alice_files = storage.list_files("user_alice")
    print(f"Files for user_alice: {alice_files}")

    retrieved_content = storage.retrieve_file("user_alice", "notes.txt", "alice_strong_password_123")
    print(f"Retrieved 'notes.txt' for alice: '{retrieved_content}'")
    assert retrieved_content == users_data["user_alice"]["files"]["notes.txt"]

    retrieved_content_bob = storage.retrieve_file("user_bob", "shopping_list.txt", "bob_secure_phrase_456")
    print(f"Retrieved 'shopping_list.txt' for bob: '{retrieved_content_bob}'")
    assert retrieved_content_bob == users_data["user_bob"]["files"]["shopping_list.txt"]

    print("\n--- Testing Error Handling ---")
    try:
        storage.retrieve_file("user_alice", "notes.txt", "wrong_password")
    except ValueError as e:
        print(f"Successfully caught error: {e}")

    try:
        storage.retrieve_file("user_alice", "non_existent_file.txt", "alice_strong_password_123")
    except FileNotFoundError as e:
        print(f"Successfully caught error: {e}")

    print("\n--- Summary ---")
    print(f"Total files stored: {total_files_stored}")
    print(f"Time taken for storage operations: {duration:.4f} seconds")

    shutil.rmtree(storage_root)
    print(f"\nCleaned up storage directory: '{storage_root}'")


if __name__ == "__main__":
    main()