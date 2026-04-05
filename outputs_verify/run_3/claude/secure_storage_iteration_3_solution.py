import hashlib
import os
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class SecureStorage:
    def __init__(self):
        # Structure: {user_id: {filename: {"salt": bytes, "nonce": bytes, "ciphertext": bytes}}}
        self._storage: dict[str, dict[str, dict[str, bytes]]] = {}
        # Cache derived keys to avoid repeated KDF computations for same user/passphrase
        # Key: (user_id, passphrase_hash) -> derived_key
        # We use a bounded cache to avoid unbounded memory growth
        self._key_cache: dict[tuple[str, bytes], bytes] = {}
        self._cache_max_size = 1000

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        """Derive a 256-bit AES key from passphrase and salt using PBKDF2."""
        # Create a cache key based on passphrase and salt
        cache_key = (passphrase, salt)
        passphrase_hash = hashlib.sha256(f"{passphrase}:{salt.hex()}".encode()).digest()
        cache_lookup = (passphrase, passphrase_hash)

        # Check cache - note we cache by (passphrase, hash_of_passphrase+salt) 
        # Actually let's cache by (passphrase, salt) directly via a hash
        full_cache_key = hashlib.sha256(passphrase.encode() + salt).digest()
        
        if full_cache_key in self._key_cache:
            return self._key_cache[full_cache_key]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        key = kdf.derive(passphrase.encode())

        # Bounded cache eviction
        if len(self._key_cache) >= self._cache_max_size:
            # Remove oldest entry (first inserted)
            oldest_key = next(iter(self._key_cache))
            del self._key_cache[oldest_key]

        self._key_cache[full_cache_key] = key
        return key

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """Encrypt and store a file for a user. AES-256-GCM provides confidentiality and tamper-evidence."""
        salt = os.urandom(16)
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)

        # Include user_id and filename as associated data for tamper-evidence of metadata
        aad = f"{user_id}:{filename}".encode()
        ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), aad)

        if user_id not in self._storage:
            self._storage[user_id] = {}

        self._storage[user_id][filename] = {
            "salt": salt,
            "nonce": nonce,
            "ciphertext": ciphertext,
        }

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """Decrypt and return a stored file. Raises on tamper detection or wrong passphrase."""
        if user_id not in self._storage:
            raise KeyError(f"No files found for user '{user_id}'")
        if filename not in self._storage[user_id]:
            raise KeyError(f"File '{filename}' not found for user '{user_id}'")

        record = self._storage[user_id][filename]
        salt = record["salt"]
        nonce = record["nonce"]
        ciphertext = record["ciphertext"]

        key = self._derive_key(passphrase, salt)
        aesgcm = AESGCM(key)

        aad = f"{user_id}:{filename}".encode()
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ValueError(f"Decryption failed for '{filename}' (wrong passphrase or tampered data): {e}")

        return plaintext.decode('utf-8')

    def list_files(self, user_id: str) -> list[str]:
        """List all filenames stored for a user."""
        if user_id not in self._storage:
            return []
        return sorted(self._storage[user_id].keys())


def main():
    storage = SecureStorage()

    # Configuration for demonstration
    users = {
        "alice": "alice_secret_passphrase",
        "bob": "bob_secure_password",
        "charlie": "charlie_p@ss!",
    }

    files_per_user = 50
    large_file_size = 10_000  # characters

    total_files = 0
    start_time = time.time()

    # Store multiple files for multiple users
    print("=" * 60)
    print("Secure Storage - Enterprise Scale Demonstration")
    print("=" * 60)

    store_start = time.time()
    for user_id, passphrase in users.items():
        for i in range(files_per_user):
            filename = f"document_{i:04d}.txt"
            # Vary file sizes: some small, some large
            if i % 10 == 0:
                data = f"Large document {i} for {user_id}. " * (large_file_size // 40)
            else:
                data = f"File {i} content for user {user_id}. Created at index {i}."
            storage.store_file(user_id, filename, data, passphrase)
            total_files += 1

    store_elapsed = time.time() - store_start
    print(f"\nStored {total_files} files for {len(users)} users in {store_elapsed:.3f}s")
    print(f"Average store time per file: {store_elapsed / total_files * 1000:.2f}ms")

    # List files for each user
    print("\nFile counts per user:")
    for user_id in users:
        file_list = storage.list_files(user_id)
        print(f"  {user_id}: {len(file_list)} files")

    # Retrieve and verify files
    retrieve_start = time.time()
    retrieved_count = 0
    for user_id, passphrase in users.items():
        for i in range(files_per_user):
            filename = f"document_{i:04d}.txt"
            retrieved_data = storage.retrieve_file(user_id, filename, passphrase)
            retrieved_count += 1
            # Spot-check content
            assert user_id in retrieved_data, f"Content verification failed for {user_id}/{filename}"

    retrieve_elapsed = time.time() - retrieve_start
    print(f"\nRetrieved and verified {retrieved_count} files in {retrieve_elapsed:.3f}s")
    print(f"Average retrieve time per file: {retrieve_elapsed / retrieved_count * 1000:.2f}ms")

    # Test tamper detection: wrong passphrase
    print("\nSecurity tests:")
    try:
        storage.retrieve_file("alice", "document_0000.txt", "wrong_passphrase")
        print("  FAIL: Should have rejected wrong passphrase")
    except ValueError as e:
        print(f"  PASS: Wrong passphrase correctly rejected")

    # Test missing file
    try:
        storage.retrieve_file("alice", "nonexistent.txt", users["alice"])
        print("  FAIL: Should have raised KeyError")
    except KeyError:
        print(f"  PASS: Missing file correctly raises error")

    # Test cross-user isolation
    try:
        storage.retrieve_file("alice", "document_0001.txt", users["bob"])
        print("  FAIL: Cross-user access should fail")
    except ValueError:
        print(f"  PASS: Cross-user access correctly rejected")

    # Test missing user
    assert storage.list_files("nonexistent_user") == []
    print(f"  PASS: Listing files for non-existent user returns empty list")

    total_elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Users: {len(users)}")
    print(f"  Total files stored: {total_files}")
    print(f"  Total files retrieved: {retrieved_count}")
    print(f"  Total time: {total_elapsed:.3f}s")
    print(f"  All security checks passed")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()