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
        # Cache derived keys to avoid repeated KDF computation for same user/passphrase combo
        # Key: (user_id, salt_hex, passphrase) -> derived_key
        self._key_cache: dict[tuple[str, str, str], bytes] = {}

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        cache_key = (salt.hex(), passphrase)
        if cache_key in self._key_cache:
            return self._key_cache[cache_key]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        key = kdf.derive(passphrase.encode("utf-8"))
        self._key_cache[cache_key] = key
        return key

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = self._derive_key(passphrase, salt)

        aesgcm = AESGCM(key)
        # Use filename as associated data for additional tamper evidence
        aad = f"{user_id}:{filename}".encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), aad)

        if user_id not in self._storage:
            self._storage[user_id] = {}

        self._storage[user_id][filename] = {
            "salt": salt,
            "nonce": nonce,
            "ciphertext": ciphertext,
        }

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
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
        aad = f"{user_id}:{filename}".encode("utf-8")

        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception:
            raise ValueError("Decryption failed: invalid passphrase or data has been tampered with")

        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> list[str]:
        if user_id not in self._storage:
            return []
        return sorted(self._storage[user_id].keys())


def main():
    storage = SecureStorage()

    users = {
        "alice": "alice_secret_passphrase",
        "bob": "bob_secure_password",
        "charlie": "charlie_p@ss!",
    }

    files_per_user = 50
    total_files = 0

    print("=" * 60)
    print("Secure Storage - Third Iteration Demo")
    print("=" * 60)

    # Store files
    start_time = time.time()

    for user_id, passphrase in users.items():
        for i in range(files_per_user):
            filename = f"document_{i:04d}.txt"
            content = f"This is {user_id}'s file #{i}. " + ("Confidential data. " * 20)
            storage.store_file(user_id, filename, content, passphrase)
            total_files += 1

    store_time = time.time() - start_time
    print(f"\nStored {total_files} files for {len(users)} users in {store_time:.3f}s")
    print(f"Average store time per file: {store_time / total_files * 1000:.2f}ms")

    # List files
    for user_id in users:
        file_list = storage.list_files(user_id)
        print(f"\n{user_id} has {len(file_list)} files: [{file_list[0]}, ..., {file_list[-1]}]")

    # Retrieve files
    start_time = time.time()
    retrieve_count = 0

    for user_id, passphrase in users.items():
        for i in range(files_per_user):
            filename = f"document_{i:04d}.txt"
            content = storage.retrieve_file(user_id, filename, passphrase)
            assert user_id in content
            assert f"file #{i}" in content
            retrieve_count += 1

    retrieve_time = time.time() - start_time
    print(f"\nRetrieved and verified {retrieve_count} files in {retrieve_time:.3f}s")
    print(f"Average retrieve time per file: {retrieve_time / retrieve_count * 1000:.2f}ms")

    # Test cross-user isolation
    print("\n--- Security Tests ---")
    try:
        storage.retrieve_file("alice", "document_0000.txt", "bob_secure_password")
        print("FAIL: Cross-user access should have been denied")
    except ValueError:
        print("PASS: Wrong passphrase correctly rejected")

    try:
        storage.retrieve_file("alice", "nonexistent.txt", "alice_secret_passphrase")
        print("FAIL: Nonexistent file should raise error")
    except KeyError:
        print("PASS: Nonexistent file correctly raises KeyError")

    # Test tamper detection
    record = storage._storage["alice"]["document_0000.txt"]
    original_ct = record["ciphertext"]
    tampered = bytearray(original_ct)
    tampered[0] ^= 0xFF
    record["ciphertext"] = bytes(tampered)
    try:
        storage.retrieve_file("alice", "document_0000.txt", "alice_secret_passphrase")
        print("FAIL: Tampered data should have been detected")
    except ValueError:
        print("PASS: Tamper detection working correctly")
    record["ciphertext"] = original_ct  # restore

    # Large file test
    print("\n--- Large File Test ---")
    large_data = "X" * (1024 * 1024)  # 1MB
    start_time = time.time()
    storage.store_file("alice", "large_file.bin", large_data, users["alice"])
    store_large = time.time() - start_time

    start_time = time.time()
    retrieved_large = storage.retrieve_file("alice", "large_file.bin", users["alice"])
    retrieve_large = time.time() - start_time

    assert retrieved_large == large_data
    print(f"1MB file: store={store_large * 1000:.2f}ms, retrieve={retrieve_large * 1000:.2f}ms")

    total_stored = sum(len(files) for files in storage._storage.values())
    print(f"\n{'=' * 60}")
    print(f"Summary: {total_stored} total files across {len(storage._storage)} users")
    print(f"All operations completed successfully.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()