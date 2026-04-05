import os
import time
import hashlib
import pathlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag

class SecureStorage:
    _KDF_ITERATIONS = 600_000
    _SALT_SIZE = 16
    _NONCE_SIZE = 12
    _KEY_SIZE = 32
    _ENCRYPTED_SUFFIX = ".enc"

    def __init__(self, storage_root: str = 'secure_storage'):
        self.storage_root = pathlib.Path(storage_root)
        self.storage_root.mkdir(exist_ok=True)
        self._backend = default_backend()

    def _get_user_dir(self, user_id: str, create: bool = False) -> pathlib.Path:
        user_hash = hashlib.sha256(user_id.encode('utf-8')).hexdigest()
        user_dir = self.storage_root / user_hash
        if create:
            user_dir.mkdir(exist_ok=True)
        return user_dir

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self._KEY_SIZE,
            salt=salt,
            iterations=self._KDF_ITERATIONS,
            backend=self._backend
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._get_user_dir(user_id, create=True)
        file_path = user_dir / (filename + self._ENCRYPTED_SUFFIX)
        
        salt = os.urandom(self._SALT_SIZE)
        key = self._derive_key(passphrase, salt)
        
        aesgcm = AESGCM(key)
        nonce = os.urandom(self._NONCE_SIZE)
        
        encoded_data = data.encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, encoded_data, None)
        
        with open(file_path, 'wb') as f:
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        user_dir = self._get_user_dir(user_id)
        file_path = user_dir / (filename + self._ENCRYPTED_SUFFIX)

        if not file_path.is_file():
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'.")

        with open(file_path, 'rb') as f:
            salt = f.read(self._SALT_SIZE)
            nonce = f.read(self._NONCE_SIZE)
            ciphertext = f.read()

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)

        try:
            decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_data.decode('utf-8')
        except InvalidTag:
            raise ValueError("Invalid passphrase or file has been tampered with.")

    def list_files(self, user_id: str) -> list[str]:
        user_dir = self._get_user_dir(user_id)
        if not user_dir.exists():
            return []
        
        files = [
            p.name[:-len(self._ENCRYPTED_SUFFIX)]
            for p in user_dir.iterdir()
            if p.is_file() and p.name.endswith(self._ENCRYPTED_SUFFIX)
        ]
        return sorted(files)

def main():
    storage = SecureStorage(storage_root='secure_storage_iteration_3')
    
    users = {
        "alice": "AlicePassword123!",
        "bob": "BobSecretPhrase456#",
        "charlie": "CharlieKeyWord789@"
    }
    
    files_to_store = {
        "report.txt": "This is the confidential quarterly report.",
        "notes.txt": "Meeting notes: Project Phoenix is a go.",
        "large_document.log": "log entry " * 100000 
    }
    
    print("--- Starting Secure Storage Operations ---")
    start_time = time.monotonic()
    
    files_stored_count = 0
    for user_id, passphrase in users.items():
        for filename, content in files_to_store.items():
            storage.store_file(user_id, f"{user_id}_{filename}", content, passphrase)
            files_stored_count += 1
            
    files_retrieved_count = 0
    verification_errors = 0
    
    for user_id, passphrase in users.items():
        user_files = storage.list_files(user_id)
        for filename in user_files:
            original_filename_key = filename.split('_', 1)[1]
            original_content = files_to_store.get(original_filename_key)
            
            retrieved_content = storage.retrieve_file(user_id, filename, passphrase)
            files_retrieved_count += 1
            
            if retrieved_content != original_content:
                verification_errors += 1

    end_time = time.monotonic()
    
    print("\n--- Testing Failure Cases ---")
    try:
        storage.retrieve_file("alice", "alice_report.txt", "WrongPassword")
    except ValueError as e:
        print(f"Successfully caught expected error (wrong passphrase): {e}")

    try:
        storage.retrieve_file("alice", "non_existent_file.txt", users["alice"])
    except FileNotFoundError as e:
        print(f"Successfully caught expected error (file not found): {e}")

    print("\n--- Summary ---")
    print(f"Total files stored: {files_stored_count}")
    print(f"Total files retrieved and verified: {files_retrieved_count}")
    print(f"Verification errors: {verification_errors}")
    print(f"Total time taken: {end_time - start_time:.4f} seconds")
    
    alice_files = storage.list_files("alice")
    print(f"\nFiles for user 'alice': {alice_files}")

if __name__ == "__main__":
    main()