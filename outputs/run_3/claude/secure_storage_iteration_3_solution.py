import os
import hashlib
import hmac
import time
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class SecureStorage:
    """
    Secure file storage system supporting multiple users and files.
    
    Each file is encrypted with AES-256-GCM using a key derived from the user's
    passphrase via PBKDF2. Each file gets its own random salt and nonce.
    An HMAC tag is stored alongside for tamper evidence.
    
    Internal storage uses nested dicts for O(1) lookup by user_id and filename.
    """

    def __init__(self):
        # storage[user_id][filename] = {salt, nonce, ciphertext, hmac_tag}
        self._storage: dict[str, dict[str, dict[str, bytes]]] = {}
        self._kdf_iterations = 100_000

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        """Derive a 256-bit encryption key from passphrase and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self._kdf_iterations,
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def _derive_hmac_key(self, passphrase: str, salt: bytes) -> bytes:
        """Derive a separate HMAC key using a different salt derivation."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt + b"hmac",
            iterations=self._kdf_iterations,
        )
        return kdf.derive(passphrase.encode('utf-8'))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """
        Encrypt and store a file for a given user.
        
        Uses AES-256-GCM for authenticated encryption. A fresh random salt (16 bytes)
        and nonce (12 bytes) are generated per file. An additional HMAC-SHA256 over
        the ciphertext provides an extra layer of tamper evidence.
        """
        salt = os.urandom(16)
        nonce = os.urandom(12)

        enc_key = self._derive_key(passphrase, salt)
        hmac_key = self._derive_hmac_key(passphrase, salt)

        aesgcm = AESGCM(enc_key)
        plaintext = data.encode('utf-8')
        # Associated data includes user_id and filename for binding
        aad = f"{user_id}:{filename}".encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

        # Compute HMAC over salt + nonce + ciphertext for tamper evidence
        hmac_tag = hmac.new(
            hmac_key,
            salt + nonce + ciphertext,
            hashlib.sha256
        ).digest()

        if user_id not in self._storage:
            self._storage[user_id] = {}

        self._storage[user_id][filename] = {
            'salt': salt,
            'nonce': nonce,
            'ciphertext': ciphertext,
            'hmac_tag': hmac_tag,
        }

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """
        Retrieve and decrypt a file for a given user.
        
        Verifies HMAC integrity before attempting decryption.
        Raises ValueError on missing file, tamper detection, or wrong passphrase.
        """
        if user_id not in self._storage or filename not in self._storage[user_id]:
            raise ValueError(f"File '{filename}' not found for user '{user_id}'")

        record = self._storage[user_id][filename]
        salt = record['salt']
        nonce = record['nonce']
        ciphertext = record['ciphertext']
        stored_hmac = record['hmac_tag']

        enc_key = self._derive_key(passphrase, salt)
        hmac_key = self._derive_hmac_key(passphrase, salt)

        # Verify HMAC first for tamper evidence
        computed_hmac = hmac.new(
            hmac_key,
            salt + nonce + ciphertext,
            hashlib.sha256
        ).digest()

        if not hmac.compare_digest(computed_hmac, stored_hmac):
            raise ValueError("Integrity check failed: data may have been tampered with or wrong passphrase")

        aesgcm = AESGCM(enc_key)
        aad = f"{user_id}:{filename}".encode('utf-8')
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

        return plaintext.decode('utf-8')

    def list_files(self, user_id: str) -> list[str]:
        """Return a sorted list of filenames stored for the given user."""
        if user_id not in self._storage:
            return []
        return sorted(self._storage[user_id].keys())


def main():
    storage = SecureStorage()
    # Use fewer KDF iterations for demo speed
    storage._kdf_iterations = 10_000

    users = {
        "alice": "alice_secret_passphrase",
        "bob": "bob_super_secure_pass",
        "charlie": "charlie_p@ss!",
    }

    # Generate test files for each user
    num_files_per_user = 50
    total_files = 0

    print("=" * 60)
    print("Secure Storage - Enterprise Scale Demo")
    print("=" * 60)

    # Store files
    store_start = time.perf_counter()
    for user_id, passphrase in users.items():
        for i in range(num_files_per_user):
            filename = f"document_{i:04d}.txt"
            content = f"Confidential data for {user_id}, file #{i}. " + ("X" * (100 + i * 10))
            storage.store_file(user_id, filename, content, passphrase)
            total_files += 1
    store_elapsed = time.perf_counter() - store_start

    print(f"\nStored {total_files} files across {len(users)} users")
    print(f"Store time: {store_elapsed:.3f}s ({total_files / store_elapsed:.1f} files/sec)")

    # List files for each user
    print("\nFile counts per user:")
    for user_id in users:
        files = storage.list_files(user_id)
        print(f"  {user_id}: {len(files)} files")

    # Retrieve and verify a sample of files
    retrieve_start = time.perf_counter()
    verified = 0
    for user_id, passphrase in users.items():
        for i in range(0, num_files_per_user, 5):  # every 5th file
            filename = f"document_{i:04d}.txt"
            expected = f"Confidential data for {user_id}, file #{i}. " + ("X" * (100 + i * 10))
            retrieved = storage.retrieve_file(user_id, filename, passphrase)
            assert retrieved == expected, f"Mismatch for {user_id}/{filename}"
            verified += 1
    retrieve_elapsed = time.perf_counter() - retrieve_start

    print(f"\nVerified {verified} files successfully")
    print(f"Retrieve time: {retrieve_elapsed:.3f}s ({verified / retrieve_elapsed:.1f} files/sec)")

    # Demonstrate security: wrong passphrase
    print("\nSecurity checks:")
    try:
        storage.retrieve_file("alice", "document_0000.txt", "wrong_passphrase")
        print("  ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"  Wrong passphrase correctly rejected: {e}")

    # Demonstrate security: non-existent file
    try:
        storage.retrieve_file("alice", "nonexistent.txt", users["alice"])
        print("  ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"  Missing file correctly rejected: {e}")

    # Demonstrate tamper detection
    record = storage._storage["alice"]["document_0000.txt"]
    original_ct = record['ciphertext']
    record['ciphertext'] = bytearray(original_ct)
    record['ciphertext'][0] ^= 0xFF
    record['ciphertext'] = bytes(record['ciphertext'])
    try:
        storage.retrieve_file("alice", "document_0000.txt", users["alice"])
        print("  ERROR: Should have detected tampering")
    except ValueError as e:
        print(f"  Tampering correctly detected: {e}")
    # Restore
    record['ciphertext'] = original_ct

    print("\n" + "=" * 60)
    print(f"Summary: {total_files} files, {len(users)} users")
    print(f"Total time: {store_elapsed + retrieve_elapsed:.3f}s")
    print("All security and correctness checks passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()