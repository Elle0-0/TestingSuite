import os
import json
import time
import shutil
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

ROOT_DIR = "secure_storage_v3"
SALT_SIZE = 16
KEY_SIZE_BYTES = 32
NONCE_SIZE_BYTES = 12
TAG_SIZE_BYTES = 16
KDF_ITERATIONS = 480000

class SecureStorage:
    def __init__(self, root_dir: str = ROOT_DIR):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def _get_paths(self, user_id: str) -> tuple[str, str, str, str, str]:
        safe_user_id = hashlib.sha256(user_id.encode('utf-8')).hexdigest()
        user_dir = os.path.join(self.root_dir, safe_user_id)
        files_dir = os.path.join(user_dir, "files")
        salt_path = os.path.join(user_dir, "master.salt")
        manifest_path = os.path.join(user_dir, "manifest.enc")
        filenames_path = os.path.join(user_dir, "index.json")
        return user_dir, files_dir, salt_path, manifest_path, filenames_path

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE_BYTES,
            salt=salt,
            iterations=KDF_ITERATIONS,
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def _read_manifest(self, user_id: str, passphrase: str) -> dict:
        _ , _, salt_path, manifest_path, _ = self._get_paths(user_id)
        
        if not os.path.exists(salt_path):
            return {}

        with open(salt_path, 'rb') as f:
            salt = f.read()

        master_key = self._derive_key(passphrase, salt)
        
        try:
            with open(manifest_path, 'rb') as f:
                manifest_nonce = f.read(NONCE_SIZE_BYTES)
                encrypted_manifest_blob = f.read()
        except FileNotFoundError:
            return {}

        aesgcm = AESGCM(master_key)
        try:
            decrypted_manifest_json = aesgcm.decrypt(
                manifest_nonce,
                encrypted_manifest_blob,
                None
            )
            return json.loads(decrypted_manifest_json.decode('utf-8'))
        except InvalidTag:
            raise ValueError("Invalid passphrase or tampered manifest")

    def _write_manifest(self, user_id: str, passphrase: str, manifest: dict, salt: bytes):
        _ , _, _, manifest_path, _ = self._get_paths(user_id)
        master_key = self._derive_key(passphrase, salt)
        
        manifest_json = json.dumps(manifest).encode('utf-8')
        
        manifest_nonce = os.urandom(NONCE_SIZE_BYTES)
        aesgcm = AESGCM(master_key)
        
        encrypted_blob = aesgcm.encrypt(manifest_nonce, manifest_json, None)

        with open(manifest_path, 'wb') as f:
            f.write(manifest_nonce)
            f.write(encrypted_blob)

    def _read_filenames(self, user_id: str) -> list[str]:
        *_, filenames_path = self._get_paths(user_id)
        try:
            with open(filenames_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_filenames(self, user_id: str, filenames: list[str]):
        *_, filenames_path = self._get_paths(user_id)
        with open(filenames_path, 'w', encoding='utf-8') as f:
            json.dump(sorted(filenames), f)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir, files_dir, salt_path, _, _ = self._get_paths(user_id)
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)
        
        if not os.path.exists(salt_path):
            salt = os.urandom(SALT_SIZE)
            with open(salt_path, 'wb') as f:
                f.write(salt)
            manifest = {}
            filenames = []
        else:
            with open(salt_path, 'rb') as f:
                salt = f.read()
            manifest = self._read_manifest(user_id, passphrase)
            filenames = self._read_filenames(user_id)

        file_key = AESGCM.generate_key(bit_length=256)
        file_nonce = os.urandom(NONCE_SIZE_BYTES)
        aesgcm = AESGCM(file_key)
        
        encrypted_blob = aesgcm.encrypt(file_nonce, data.encode('utf-8'), None)

        file_id = hashlib.sha256(filename.encode('utf-8')).hexdigest()
        file_path = os.path.join(files_dir, file_id)

        with open(file_path, 'wb') as f:
            f.write(file_nonce)
            f.write(encrypted_blob)

        manifest[filename] = {
            "id": file_id,
            "key": file_key.hex(),
        }
        
        self._write_manifest(user_id, passphrase, manifest, salt)

        if filename not in filenames:
            filenames.append(filename)
            self._write_filenames(user_id, filenames)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        _ , files_dir, _, _, _ = self._get_paths(user_id)
        manifest = self._read_manifest(user_id, passphrase)
        
        file_meta = manifest.get(filename)
        if not file_meta:
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'")

        file_key = bytes.fromhex(file_meta["key"])
        file_path = os.path.join(files_dir, file_meta["id"])

        with open(file_path, 'rb') as f:
            file_nonce = f.read(NONCE_SIZE_BYTES)
            encrypted_blob = f.read()

        aesgcm = AESGCM(file_key)
        try:
            decrypted_data = aesgcm.decrypt(file_nonce, encrypted_blob, None)
            return decrypted_data.decode('utf-8')
        except InvalidTag:
            raise IOError("File is corrupt or has been tampered with")

    def list_files(self, user_id: str) -> list[str]:
        return self._read_filenames(user_id)

def main():
    if os.path.exists(ROOT_DIR):
        shutil.rmtree(ROOT_DIR)

    storage = SecureStorage()
    
    users_data = {
        "user_alice@example.com": {
            "passphrase": "alice's-strong-password-123",
            "files": {
                "report.txt": "This is the annual financial report.",
                "notes.txt": "Meeting notes: project alpha is on schedule.",
                "large_doc.txt": "a" * (1024 * 50) 
            }
        },
        "user_bob@example.com": {
            "passphrase": "bob's-even-stronger-password-456!",
            "files": {
                "research.dat": "{\"key\": \"value\", \"data\": [1,2,3]}",
                "todos.json": "[\"buy milk\", \"call mom\"]"
            }
        }
    }
    
    start_time = time.monotonic()
    total_files = 0
    
    for user_id, user_info in users_data.items():
        passphrase = user_info["passphrase"]
        for filename, data in user_info["files"].items():
            storage.store_file(user_id, filename, data, passphrase)
            total_files += 1
            
    end_time = time.monotonic()

    print("--- Summary ---")
    print(f"Total files stored: {total_files}")
    print(f"Time taken to store: {end_time - start_time:.4f} seconds")

    for user_id, user_info in users_data.items():
        passphrase = user_info["passphrase"]
        assert sorted(storage.list_files(user_id)) == sorted(user_info["files"].keys())
        for filename, original_data in user_info["files"].items():
            retrieved_data = storage.retrieve_file(user_id, filename, passphrase)
            assert retrieved_data == original_data
    
    try:
        storage.retrieve_file(
            "user_alice@example.com", 
            "report.txt", 
            "wrong-password"
        )
    except ValueError:
        pass

    try:
        storage.retrieve_file(
            "user_bob@example.com", 
            "ghost.file", 
            users_data["user_bob@example.com"]["passphrase"]
        )
    except FileNotFoundError:
        pass

    shutil.rmtree(ROOT_DIR)


if __name__ == "__main__":
    main()