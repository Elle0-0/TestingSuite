import os
import time
import hashlib
import shutil
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
except ImportError:
    print("Fatal Error: The 'cryptography' library is not installed.")
    print("Please install it by running: pip install cryptography")
    exit(1)

class SecureStorage:
    _SALT_SIZE = 16
    _NONCE_SIZE = 12
    _KEY_LEN = 32
    _PBKDF2_ITERATIONS = 600_000

    def __init__(self, base_dir: str = "secure_storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt,
            self._PBKDF2_ITERATIONS,
            dklen=self._KEY_LEN
        )

    def _validate_path_component(self, component: str, component_name: str):
        if not component or ".." in component or "/" in component or "\\" in component:
            raise ValueError(f"Invalid {component_name} provided.")

    def _get_user_path(self, user_id: str) -> Path:
        self._validate_path_component(user_id, "user_id")
        return self.base_dir / user_id

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        self._validate_path_component(filename, "filename")
        user_dir = self._get_user_path(user_id)
        user_dir.mkdir(exist_ok=True)
        file_path = user_dir / f"{filename}.enc"

        salt = os.urandom(self._SALT_SIZE)
        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        nonce = os.urandom(self._NONCE_SIZE)

        ciphertext_with_tag = aesgcm.encrypt(nonce, data.encode('utf-8'), None)

        with file_path.open('wb') as f:
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext_with_tag)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        self._validate_path_component(filename, "filename")
        user_dir = self._get_user_path(user_id)
        file_path = user_dir / f"{filename}.enc"

        if not file_path.is_file():
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'.")

        with file_path.open('rb') as f:
            salt = f.read(self._SALT_SIZE)
            nonce = f.read(self._NONCE_SIZE)
            ciphertext_with_tag = f.read()

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)

        try:
            decrypted_data = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            return decrypted_data.decode('utf-8')
        except InvalidTag:
            raise ValueError("Decryption failed: Invalid passphrase or tampered file.")

    def list_files(self, user_id: str) -> list[str]:
        user_dir = self._get_user_path(user_id)
        if not user_dir.is_dir():
            return []

        return sorted([p.stem for p in user_dir.glob('*.enc') if p.is_file()])

def main():
    STORAGE_DIR = "secure_storage_demo_3"
    shutil.rmtree(STORAGE_DIR, ignore_errors=True)

    storage = SecureStorage(base_dir=STORAGE_DIR)
    files_stored_count = 0
    
    print("--- Secure Storage: Third Iteration Demo ---")
    start_time = time.monotonic()

    users_data = {
        "alice_42": {
            "pass": "r4bb1t-h0l3-p@ssw0rd",
            "files": {
                "report.txt": "This is the confidential quarterly report.",
                "shopping_list.txt": "Carrots, Tea, Mad Hatter's hat.",
                "notes_on_bob.txt": "Bob seems to be building something big."
            }
        },
        "bob_the_builder": {
            "pass": "c@n-w3-f1x-1t-y3s-w3-c@n",
            "files": {
                "blueprint_v1.txt": "Initial draft of the super structure.",
                "materials.csv": "Steel,1000 tons\nConcrete,5000 cubic meters\n",
                "large_project_plan.txt": "This is a large document. " * (5 * 1024 * 10)
            }
        }
    }

    for user_id, data in users_data.items():
        print(f"\nStoring {len(data['files'])} files for user '{user_id}'...")
        for filename, content in data['files'].items():
            storage.store_file(user_id, filename, content, data['pass'])
            files_stored_count += 1
    
    end_store_time = time.monotonic()
    
    print("\n--- Verification and Listing ---")
    
    # Alice's operations
    alice_id = "alice_42"
    alice_pass = users_data[alice_id]['pass']
    alice_files = storage.list_files(alice_id)
    print(f"\nFiles for '{alice_id}': {alice_files}")
    retrieved_report = storage.retrieve_file(alice_id, "report.txt", alice_pass)
    assert retrieved_report == users_data[alice_id]['files']["report.txt"]
    print(f"Successfully retrieved 'report.txt' for '{alice_id}'.")

    # Bob's operations
    bob_id = "bob_the_builder"
    bob_pass = users_data[bob_id]['pass']
    bob_files = storage.list_files(bob_id)
    print(f"\nFiles for '{bob_id}': {bob_files}")
    retrieved_large_file = storage.retrieve_file(bob_id, "large_project_plan.txt", bob_pass)
    assert retrieved_large_file == users_data[bob_id]['files']["large_project_plan.txt"]
    print(f"Successfully retrieved 'large_project_plan.txt' for '{bob_id}'.")
    
    print("\n--- Error Handling ---")
    
    try:
        storage.retrieve_file(alice_id, "report.txt", "wrong_password_123")
    except ValueError as e:
        print(f"Successfully caught expected error (wrong pass): {e}")

    try:
        storage.retrieve_file(alice_id, "ghost_file.txt", alice_pass)
    except FileNotFoundError as e:
        print(f"Successfully caught expected error (not found): {e}")

    try:
        storage.store_file(bob_id, "../backdoor.txt", "exploit", bob_pass)
    except ValueError as e:
        print(f"Successfully caught expected error (bad path): {e}")

    end_time = time.monotonic()
    
    print("\n--- Summary ---")
    print(f"Total files stored: {files_stored_count}")
    print(f"Time for storage operations: {end_store_time - start_time:.4f} seconds")
    print(f"Total time for all operations: {end_time - start_time:.4f} seconds")

    shutil.rmtree(STORAGE_DIR, ignore_errors=True)
    print(f"\nCleaned up storage directory: {STORAGE_DIR}")


if __name__ == "__main__":
    main()