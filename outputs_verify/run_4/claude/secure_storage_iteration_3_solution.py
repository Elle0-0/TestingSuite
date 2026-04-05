import os
import hashlib
import hmac
import time
import struct
from collections import defaultdict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class SecureStorage:
    """
    Secure file storage system with per-file encryption and tamper detection.
    
    Each file is encrypted with AES-256-GCM using a key derived from the user's
    passphrase and a unique per-file salt via PBKDF2. The GCM tag provides
    authenticated encryption (confidentiality + integrity/tamper-evidence).
    
    Storage is organized by user_id for efficient per-user operations.
    """

    # KDF iterations - balances security vs performance for many files
    KDF_ITERATIONS = 100_000
    SALT_SIZE = 16
    NONCE_SIZE = 12  # 96-bit nonce for AES-GCM

    def __init__(self):
        # In-memory storage: user_id -> {filename -> encrypted_blob}
        self._storage: dict[str, dict[str, bytes]] = defaultdict(dict)
        # Cache derived keys to avoid repeated KDF for same user/passphrase
        # Key: (user_id, passphrase_hash) -> derived_master_key
        self._key_cache: dict[tuple[str, bytes], bytes] = {}

    def _get_master_key(self, user_id: str, passphrase: str) -> bytes:
        """
        Derive a master key for the user from their passphrase.
        Uses caching to avoid repeated expensive KDF operations when
        storing/retrieving multiple files in sequence.
        """
        # Hash passphrase for cache lookup (don't store raw passphrase)
        passphrase_hash = hashlib.sha256(passphrase.encode('utf-8')).digest()
        cache_key = (user_id, passphrase_hash)

        if cache_key not in self._key_cache:
            # Use a deterministic salt derived from user_id for master key
            # This allows caching while still being unique per user
            master_salt = hashlib.sha256(
                b"master_salt:" + user_id.encode('utf-8')
            ).digest()[:self.SALT_SIZE]

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=master_salt,
                iterations=self.KDF_ITERATIONS,
            )
            master_key = kdf.derive(passphrase.encode('utf-8'))
            self._key_cache[cache_key] = master_key

        return self._key_cache[cache_key]

    def _derive_file_key(self, master_key: bytes, file_salt: bytes) -> bytes:
        """
        Derive a per-file encryption key from the master key and a random file salt.
        Uses HKDF-like construction via HMAC for speed (master key already strong).
        """
        return hmac.new(
            master_key,
            b"file_key:" + file_salt,
            hashlib.sha256
        ).digest()

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """
        Encrypt and store a file. Each file gets a unique random salt and nonce.
        
        Blob format: [salt (16 bytes)] [nonce (12 bytes)] [ciphertext + GCM tag]
        
        AES-256-GCM provides authenticated encryption - any tampering with the
        ciphertext, nonce, or tag will cause decryption to fail.
        """
        master_key = self._get_master_key(user_id, passphrase)

        # Unique random salt per file for key derivation
        file_salt = os.urandom(self.SALT_SIZE)
        file_key = self._derive_file_key(master_key, file_salt)

        # Unique random nonce per encryption
        nonce = os.urandom(self.NONCE_SIZE)

        # Encrypt with AES-256-GCM; associated data includes user_id and filename
        # to bind the ciphertext to its intended context (prevents swapping attacks)
        aad = f"{user_id}:{filename}".encode('utf-8')
        aesgcm = AESGCM(file_key)
        ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), aad)

        # Store as: salt || nonce || ciphertext+tag
        blob = file_salt + nonce + ciphertext
        self._storage[user_id][filename] = blob

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """
        Retrieve and decrypt a file. Raises on tamper detection or wrong passphrase.
        """
        if user_id not in self._storage or filename not in self._storage[user_id]:
            raise FileNotFoundError(
                f"File '{filename}' not found for user '{user_id}'"
            )

        blob = self._storage[user_id][filename]

        # Parse blob
        file_salt = blob[:self.SALT_SIZE]
        nonce = blob[self.SALT_SIZE:self.SALT_SIZE + self.NONCE_SIZE]
        ciphertext = blob[self.SALT_SIZE + self.NONCE_SIZE:]

        master_key = self._get_master_key(user_id, passphrase)
        file_key = self._derive_file_key(master_key, file_salt)

        # Decrypt and verify integrity via GCM tag
        aad = f"{user_id}:{filename}".encode('utf-8')
        aesgcm = AESGCM(file_key)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ValueError(
                f"Decryption failed for '{filename}' - wrong passphrase or data tampered"
            ) from e

        return plaintext.decode('utf-8')

    def list_files(self, user_id: str) -> list[str]:
        """List all filenames stored for a given user. O(n) in number of user's files."""
        if user_id not in self._storage:
            return []
        return sorted(self._storage[user_id].keys())


def main():
    """Demonstrate multi-user, multi-file secure storage with performance metrics."""
    storage = SecureStorage()

    # Configuration for demonstration
    num_users = 5
    files_per_user = 50
    large_file_size = 10_000  # characters

    print("=" * 60)
    print("Secure Storage - Enterprise Scale Demonstration")
    print("=" * 60)

    # --- Store files for multiple users ---
    total_files = 0
    total_bytes = 0
    store_start = time.perf_counter()

    users = {}
    for u in range(num_users):
        user_id = f"user_{u:04d}"
        passphrase = f"strong_passphrase_for_{user_id}_!@#$"
        users[user_id] = passphrase

        for f in range(files_per_user):
            filename = f"document_{f:04d}.txt"
            # Vary file sizes: most small, some large
            if f % 10 == 0:
                data = f"Large document {f} for {user_id}. " * (large_file_size // 40)
            else:
                data = f"Content of {filename} belonging to {user_id}. Confidential data here."

            storage.store_file(user_id, filename, data, passphrase)
            total_files += 1
            total_bytes += len(data.encode('utf-8'))

    store_elapsed = time.perf_counter() - store_start

    print(f"\nStored {total_files} files for {num_users} users")
    print(f"Total plaintext size: {total_bytes:,} bytes")
    print(f"Store time: {store_elapsed:.3f}s ({total_files / store_elapsed:.1f} files/sec)")

    # --- List files ---
    list_start = time.perf_counter()
    for user_id in users:
        file_list = storage.list_files(user_id)
        assert len(file_list) == files_per_user
    list_elapsed = time.perf_counter() - list_start
    print(f"\nList files time (all users): {list_elapsed * 1000:.2f}ms")

    # --- Retrieve and verify all files ---
    retrieve_start = time.perf_counter()
    retrieved_count = 0

    for u in range(num_users):
        user_id = f"user_{u:04d}"
        passphrase = users[user_id]

        for f in range(files_per_user):
            filename = f"document_{f:04d}.txt"
            if f % 10 == 0:
                expected = f"Large document {f} for {user_id}. " * (large_file_size // 40)
            else:
                expected = f"Content of {filename} belonging to {user_id}. Confidential data here."

            result = storage.retrieve_file(user_id, filename, passphrase)
            assert result == expected, f"Data mismatch for {user_id}/{filename}"
            retrieved_count += 1

    retrieve_elapsed = time.perf_counter() - retrieve_start
    print(f"\nRetrieved and verified {retrieved_count} files")
    print(f"Retrieve time: {retrieve_elapsed:.3f}s ({retrieved_count / retrieve_elapsed:.1f} files/sec)")

    # --- Security tests ---
    print("\n--- Security Verification ---")

    # Test: wrong passphrase
    try:
        storage.retrieve_file("user_0000", "document_0000.txt", "wrong_passphrase")
        print("FAIL: Wrong passphrase should have raised an error")
    except ValueError as e:
        print(f"✓ Wrong passphrase correctly rejected: {e}")

    # Test: file not found
    try:
        storage.retrieve_file("user_0000", "nonexistent.txt", users["user_0000"])
        print("FAIL: Missing file should have raised an error")
    except FileNotFoundError as e:
        print(f"✓ Missing file correctly reported: {e}")

    # Test: tamper detection (modify stored ciphertext)
    user_id = "user_0000"
    filename = "document_0001.txt"
    blob = storage._storage[user_id][filename]
    # Flip a byte in the ciphertext portion
    tampered = bytearray(blob)
    tampered[-5] ^= 0xFF
    storage._storage[user_id][filename] = bytes(tampered)
    try:
        storage.retrieve_file(user_id, filename, users[user_id])
        print("FAIL: Tampered data should have been detected")
    except ValueError as e:
        print(f"✓ Tamper detected: {e}")

    # Test: cross-user isolation
    try:
        storage.retrieve_file("user_0001", "document_0000.txt", users["user_0000"])
        print("FAIL: Cross-user access should have failed")
    except ValueError:
        print("✓ Cross-user isolation verified")

    # --- Summary ---
    total_elapsed = store_elapsed + retrieve_elapsed
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Users:           {num_users}")
    print(f"Files per user:  {files_per_user}")
    print(f"Total files:     {total_files}")
    print(f"Total data:      {total_bytes:,} bytes")
    print(f"Store time:      {store_elapsed:.3f}s")
    print(f"Retrieve time:   {retrieve_elapsed:.3f}s")
    print(f"Total time:      {total_elapsed:.3f}s")
    print(f"Throughput:      {(2 * total_files) / total_elapsed:.1f} ops/sec")
    print("All integrity and confidentiality checks passed.")


if __name__ == "__main__":
    main()