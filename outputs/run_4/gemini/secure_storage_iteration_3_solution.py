import os
import shutil
import time
import hashlib
import tempfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

class SecureStorage:
    """
    A class to securely store and retrieve files for multiple users,
    designed for scalability and performance.
    """
    _SALT_SIZE = 16
    _NONCE_SIZE = 12
    _KEY_SIZE = 32
    _PBKDF2_ITERATIONS = 600_000
    _STORAGE_SUBDIR = "secure_storage_data"
    _FILE_SUFFIX = ".enc"

    def __init__(self, base_path: str):
        """
        Initializes the SecureStorage system.

        Args:
            base_path: The root directory for storing all user files.
        """
        self.storage_dir = os.path.join(base_path, self._STORAGE_SUBDIR)
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_user_path(self, user_id: str) -> str:
        """Constructs and creates the directory path for a given user."""
        if not user_id or not user_id.isalnum():
            raise ValueError("User ID must be a non-empty alphanumeric string.")
        path = os.path.join(self.storage_dir, user_id)
        os.makedirs(path, exist_ok=True)
        return path

    def _validate_filename(self, filename: str) -> None:
        """Validates the filename to prevent path traversal and other issues."""
        if not filename or ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError("Invalid filename.")

    def _get_file_path(self, user_id: str, filename: str) -> str:
        """Constructs the full, secure path for a stored file."""
        self._validate_filename(filename)
        user_path = self._get_user_path(user_id)
        return os.path.join(user_path, filename + self._FILE_SUFFIX)

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        """Derives a cryptographic key from a passphrase and salt."""
        return hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt,
            self._PBKDF2_ITERATIONS,
            dklen=self._KEY_SIZE
        )

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """
        Encrypts and stores a file for a specific user.

        Args:
            user_id: The identifier for the user.
            filename: The name of the file to store.
            data: The string content of the file.
            passphrase: The passphrase to use for encryption.
        """
        file_path = self._get_file_path(user_id, filename)
        salt = os.urandom(self._SALT_SIZE)
        key = self._derive_key(passphrase, salt)
        
        aesgcm = AESGCM(key)
        nonce = os.urandom(self._NONCE_SIZE)
        
        plaintext = data.encode('utf-8')
        # Associated data authenticates user_id and filename
        associated_data = f"{user_id}:{filename}".encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

        with open(file_path, 'wb') as f:
            f.write(salt)
            f.write(nonce)
            f.write(ciphertext)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """
        Retrieves and decrypts a file for a specific user.

        Args:
            user_id: The identifier for the user.
            filename: The name of the file to retrieve.
            passphrase: The passphrase used for encryption.

        Returns:
            The decrypted string content of the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the passphrase is incorrect or the file is corrupted.
        """
        file_path = self._get_file_path(user_id, filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{filename}' not found for user '{user_id}'.")

        with open(file_path, 'rb') as f:
            content = f.read()

        salt = content[:self._SALT_SIZE]
        nonce = content[self._SALT_SIZE : self._SALT_SIZE + self._NONCE_SIZE]
        ciphertext = content[self._SALT_SIZE + self._NONCE_SIZE:]

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)
        
        associated_data = f"{user_id}:{filename}".encode('utf-8')

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
            return plaintext.decode('utf-8')
        except InvalidTag:
            raise ValueError("Invalid passphrase or corrupted file.")

    def list_files(self, user_id: str) -> list[str]:
        """
        Lists all stored files for a specific user.

        Args:
            user_id: The identifier for the user.

        Returns:
            A sorted list of filenames.
        """
        user_path = os.path.join(self.storage_dir, user_id)
        if not os.path.isdir(user_path):
            return []
        
        files = [
            f.removesuffix(self._FILE_SUFFIX)
            for f in os.listdir(user_path)
            if f.endswith(self._FILE_SUFFIX) and os.path.isfile(os.path.join(user_path, f))
        ]
        files.sort()
        return files

def main():
    """
    Demonstrates the functionality of the SecureStorage class.
    """
    base_dir = tempfile.mkdtemp()
    print(f"Using temporary storage directory: {base_dir}")
    
    storage = SecureStorage(base_dir)
    files_stored_count = 0
    
    users = {
        "alice": "alice_strong_password_123",
        "bob": "bob_secure_passphrase_456",
        "charlie": "charlie_secret_key_789"
    }

    files_to_store = {
        "report.txt": "This is the confidential quarterly report.",
        "notes.md": "# Meeting Notes\n\n- Discuss project alpha\n- Review budget",
        "code.py": "import sys\n\nprint('Hello, ' + sys.argv[1])",
        "large_document.txt": "This is a larger document to simulate a more significant file size. " * 1000,
    }

    start_time = time.perf_counter()

    # --- Store files for multiple users ---
    for user_id, passphrase in users.items():
        for filename, data in files_to_store.items():
            storage.store_file(user_id, filename, data, passphrase)
            files_stored_count += 1
    
    # --- Retrieve and verify files ---
    print("\n--- Verification ---")
    user_to_test = "bob"
    pass_to_test = users[user_to_test]
    
    # List files for a user
    bob_files = storage.list_files(user_to_test)
    print(f"Files for {user_to_test}: {bob_files}")
    assert sorted(bob_files) == sorted(list(files_to_store.keys()))

    # Retrieve a specific file
    filename_to_retrieve = "report.txt"
    retrieved_data = storage.retrieve_file(user_to_test, filename_to_retrieve, pass_to_test)
    print(f"Successfully retrieved '{filename_to_retrieve}' for {user_to_test}.")
    assert retrieved_data == files_to_store[filename_to_retrieve]
    
    # --- Test failure cases ---
    print("\n--- Failure Case Testing ---")
    try:
        storage.retrieve_file(user_to_test, filename_to_retrieve, "wrong_password")
    except ValueError as e:
        print(f"Caught expected error (wrong passphrase): {e}")

    try:
        storage.retrieve_file(user_to_test, "non_existent_file.doc", pass_to_test)
    except FileNotFoundError as e:
        print(f"Caught expected error (file not found): {e}")

    try:
        storage.store_file("eve", "../../../etc/passwd", "malicious", "hack")
    except ValueError as e:
        print(f"Caught expected error (invalid filename): {e}")

    end_time = time.perf_counter()
    duration = end_time - start_time

    print("\n--- Summary ---")
    print(f"Total files stored: {files_stored_count}")
    print(f"Total time taken: {duration:.4f} seconds")

    # Clean up the temporary directory
    try:
        shutil.rmtree(base_dir)
        print(f"\nCleaned up temporary storage directory: {base_dir}")
    except OSError as e:
        print(f"Error cleaning up directory {base_dir}: {e}")

if __name__ == "__main__":
    main()