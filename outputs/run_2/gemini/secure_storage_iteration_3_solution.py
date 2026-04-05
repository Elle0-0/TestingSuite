import os
import json
import time
import shutil
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

class SecureStorage:
    _STORAGE_ROOT = "secure_storage_data"
    _KDF_ITERATIONS = 480000
    _METADATA_FILENAME = "metadata.json"

    def __init__(self):
        os.makedirs(self._STORAGE_ROOT, exist_ok=True)

    def _get_user_path(self, user_id: str) -> str:
        safe_user_id = hashlib.sha256(user_id.encode('utf-8')).hexdigest()
        return os.path.join(self._STORAGE_ROOT, safe_user_id)

    def _get_metadata_path(self, user_id: str) -> str:
        return os.path.join(self._get_user_path(user_id), self._METADATA_FILENAME)

    def _load_metadata(self, user_id: str) -> dict:
        metadata_path = self._get_metadata_path(user_id)
        if not os.path.exists(metadata_path):
            return {"files": {}}
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"files": {}}

    def _save_metadata(self, user_id: str, metadata: dict) -> None:
        user_path = self._get_user_path(user_id)
        os.makedirs(user_path, exist_ok=True)
        metadata_path = self._get_metadata_path(user_id)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self._KDF_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        metadata = self._load_metadata(user_id)
        if filename in metadata["files"]:
            raise FileExistsError(f"File '{filename}' already exists for user '{user_id}'.")

        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        
        encoded_data = data.encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, encoded_data, None)

        storage_id = os.urandom(16).hex()
        user_path = self._get_user_path(user_id)
        os.makedirs(user_path, exist_ok=True)
        storage_path = os.path.join(user_path, storage_id)

        with open(storage_path, 'wb') as f:
            f.write(ciphertext)

        metadata["files"][filename] = {
            "storage_id": storage_id,
            "salt": salt.hex(),
            "nonce": nonce.hex()
        }
        self._save_metadata(user_id, metadata)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        metadata = self._load_metadata(user_id)
        file_info = metadata.get("files", {}).get(filename)

        if not file_info:
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'.")

        try:
            salt = bytes.fromhex(file_info["salt"])
            nonce = bytes.fromhex(file_info["nonce"])
            storage_id = file_info["storage_id"]
        except (KeyError, ValueError):
            raise ValueError("Metadata for file is corrupted or incomplete.")

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)

        user_path = self._get_user_path(user_id)
        storage_path = os.path.join(user_path, storage_id)

        if not os.path.exists(storage_path):
            raise FileNotFoundError("Physical storage file is missing.")
            
        with open(storage_path, 'rb') as f:
            ciphertext = f.read()

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        except InvalidTag:
            raise ValueError("Decryption failed. Invalid passphrase or tampered file.")

    def list_files(self, user_id: str) -> list[str]:
        metadata = self._load_metadata(user_id)
        return list(metadata.get("files", {}).keys())

def main():
    storage = SecureStorage()
    storage_root = getattr(storage, '_STORAGE_ROOT', 'secure_storage_data')

    if os.path.exists(storage_root):
        shutil.rmtree(storage_root)
    
    start_time = time.monotonic()
    files_stored_count = 0

    users = {
        "alice": "alice_strong_password_123",
        "bob": "bob_secure_phrase_456",
        "charlie": "charlie_secret_key_789"
    }

    files_to_store = {
        "alice": [
            ("report.txt", "This is the confidential quarterly report."),
            ("notes.txt", "Meeting notes from the secret project."),
            ("large_doc.txt", "This is a larger document simulation..." * 1000)
        ],
        "bob": [
            ("plan.doc", "The main plan document."),
            ("contacts.csv", "Name,Email\nJohn Doe,john@example.com")
        ],
        "charlie": [
            (f"log_{i}.log", f"Log entry number {i}") for i in range(10)
        ]
    }

    for user, passphrase in users.items():
        for filename, data in files_to_store.get(user, []):
            storage.store_file(user, filename, data, passphrase)
            files_stored_count += 1
    
    retrieved_content = storage.retrieve_file("alice", "report.txt", users["alice"])
    
    alice_files = storage.list_files("alice")
    bob_files = storage.list_files("bob")
    
    decryption_failed = False
    try:
        storage.retrieve_file("alice", "report.txt", "wrong_password")
    except ValueError as e:
        if "Decryption failed" in str(e):
            decryption_failed = True

    end_time = time.monotonic()
    
    print("--- Secure Storage Demo Summary ---")
    print(f"Total files stored: {files_stored_count}")
    print(f"Time taken: {end_time - start_time:.4f} seconds")
    print("\nDemonstration Results:")
    print(f"  - Files listed for 'alice': {alice_files}")
    print(f"  - Files listed for 'bob': {bob_files}")
    print(f"  - Retrieved 'alice/report.txt' successfully: {retrieved_content == files_to_store['alice'][0][1]}")
    print(f"  - Correctly failed retrieval with wrong passphrase: {decryption_failed}")
    
    if os.path.exists(storage_root):
        shutil.rmtree(storage_root)

if __name__ == '__main__':
    main()