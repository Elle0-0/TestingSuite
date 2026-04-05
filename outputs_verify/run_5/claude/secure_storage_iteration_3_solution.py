import os
import hashlib
import hmac
import time
import struct
from collections import defaultdict


class SecureStorage:
    """
    Secure file storage system with per-file encryption and tamper detection.
    
    Each file is encrypted with AES-256-CTR derived from the user's passphrase
    and a unique per-file salt. An HMAC-SHA256 tag provides tamper evidence.
    
    Storage is organized per-user using dictionaries for O(1) lookup regardless
    of the number of users or files.
    """

    def __init__(self):
        # user_id -> { filename -> encrypted_record }
        # encrypted_record = (salt, nonce, ciphertext, hmac_tag)
        self._storage: dict[str, dict[str, tuple[bytes, bytes, bytes, bytes]]] = defaultdict(dict)

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
        """
        Derive a 256-bit encryption key and a 256-bit HMAC key from
        passphrase + salt using PBKDF2-HMAC-SHA256.
        Returns (enc_key, hmac_key) each 32 bytes.
        """
        # 64 bytes total: first 32 for encryption, next 32 for HMAC
        derived = hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt,
            iterations=100_000,
            dklen=64
        )
        return derived[:32], derived[32:]

    @staticmethod
    def _aes_ctr_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
        """
        Generate a keystream using AES-256-CTR mode.
        Uses PyCryptodome if available, otherwise falls back to a pure-Python
        AES-CTR construction built on hashlib for portability.
        """
        try:
            from Crypto.Cipher import AES
            # nonce is 16 bytes; use first 8 as nonce, counter starts at 0
            cipher = AES.new(key, AES.MODE_CTR, nonce=nonce[:8])
            return cipher.encrypt(b'\x00' * length)
        except ImportError:
            pass

        # Fallback: CTR-mode stream using HMAC-SHA256 as a PRF block cipher substitute.
        # This is NOT standard AES but provides confidentiality via a keyed PRF.
        # Each block = HMAC-SHA256(key, nonce || counter)
        keystream = bytearray()
        counter = 0
        while len(keystream) < length:
            block_input = nonce + struct.pack('<Q', counter)
            block = hmac.new(key, block_input, hashlib.sha256).digest()
            keystream.extend(block)
            counter += 1
        return bytes(keystream[:length])

    @staticmethod
    def _xor_bytes(data: bytes, keystream: bytes) -> bytes:
        """XOR data with keystream."""
        return bytes(a ^ b for a, b in zip(data, keystream))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """
        Encrypt and store a file for a given user.
        
        Each file gets a fresh random salt (32 bytes) and nonce (16 bytes),
        ensuring unique keys even if the same passphrase is reused across files.
        An HMAC-SHA256 tag over (filename_bytes || ciphertext) provides tamper detection.
        """
        salt = os.urandom(32)
        nonce = os.urandom(16)

        enc_key, hmac_key = self._derive_key(passphrase, salt)

        plaintext = data.encode('utf-8')
        keystream = self._aes_ctr_keystream(enc_key, nonce, len(plaintext))
        ciphertext = self._xor_bytes(plaintext, keystream)

        # HMAC covers filename + ciphertext to bind the tag to the file identity
        tag_data = filename.encode('utf-8') + ciphertext
        hmac_tag = hmac.new(hmac_key, tag_data, hashlib.sha256).digest()

        self._storage[user_id][filename] = (salt, nonce, ciphertext, hmac_tag)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """
        Retrieve and decrypt a file. Raises an error if the file doesn't exist,
        the passphrase is wrong (HMAC verification fails), or data has been tampered with.
        """
        user_files = self._storage.get(user_id)
        if user_files is None or filename not in user_files:
            raise FileNotFoundError(
                f"No file '{filename}' found for user '{user_id}'"
            )

        salt, nonce, ciphertext, stored_tag = user_files[filename]

        enc_key, hmac_key = self._derive_key(passphrase, salt)

        # Verify integrity before decryption
        tag_data = filename.encode('utf-8') + ciphertext
        computed_tag = hmac.new(hmac_key, tag_data, hashlib.sha256).digest()

        if not hmac.compare_digest(computed_tag, stored_tag):
            raise PermissionError(
                "Integrity check failed: wrong passphrase or data has been tampered with"
            )

        keystream = self._aes_ctr_keystream(enc_key, nonce, len(ciphertext))
        plaintext = self._xor_bytes(ciphertext, keystream)

        return plaintext.decode('utf-8')

    def list_files(self, user_id: str) -> list[str]:
        """
        List all filenames stored for a given user. O(n) in the number of
        files for that user, O(1) lookup for the user bucket.
        """
        return list(self._storage.get(user_id, {}).keys())


def main():
    storage = SecureStorage()

    # Define multiple users with multiple files each
    users = {
        "alice": {
            "passphrase": "alice-strong-passphrase-2024!",
            "files": {
                "report_q1.txt": "Q1 revenue was $1.2M with 15% growth YoY.",
                "report_q2.txt": "Q2 revenue was $1.5M with 20% growth YoY.",
                "notes.txt": "Remember to update the board presentation.",
                "credentials.txt": "DB_HOST=10.0.0.5 DB_PASS=s3cret!",
            }
        },
        "bob": {
            "passphrase": "bob-secure-key-!@#$%",
            "files": {
                "project_plan.txt": "Phase 1: Design. Phase 2: Implementation. Phase 3: Testing.",
                "budget.txt": "Total budget: $500,000. Allocated: Engineering 60%, QA 25%, PM 15%.",
            }
        },
        "charlie": {
            "passphrase": "charlie-p@$$w0rd-xyz",
            "files": {}
        }
    }

    # Add a batch of files for charlie to demonstrate scaling
    for i in range(50):
        users["charlie"]["files"][f"document_{i:04d}.txt"] = (
            f"This is document number {i} with some confidential content. " * 10
        )

    print("=" * 70)
    print("Secure Storage - Third Iteration: Scaling & Multi-File Operations")
    print("=" * 70)

    # Store all files and measure time
    total_files = 0
    store_start = time.perf_counter()

    for user_id, user_data in users.items():
        passphrase = user_data["passphrase"]
        for filename, data in user_data["files"].items():
            storage.store_file(user_id, filename, data, passphrase)
            total_files += 1

    store_elapsed = time.perf_counter() - store_start

    print(f"\nStored {total_files} files across {len(users)} users "
          f"in {store_elapsed:.4f} seconds")

    # List files for each user
    print("\n--- File Listings ---")
    for user_id in users:
        file_list = storage.list_files(user_id)
        print(f"  {user_id}: {len(file_list)} file(s)")
        if len(file_list) <= 6:
            for fn in file_list:
                print(f"    - {fn}")
        else:
            for fn in file_list[:3]:
                print(f"    - {fn}")
            print(f"    ... and {len(file_list) - 3} more")

    # Retrieve and verify all files
    print("\n--- Retrieval & Verification ---")
    retrieve_start = time.perf_counter()
    errors = 0

    for user_id, user_data in users.items():
        passphrase = user_data["passphrase"]
        for filename, original_data in user_data["files"].items():
            try:
                retrieved = storage.retrieve_file(user_id, filename, passphrase)
                if retrieved != original_data:
                    print(f"  MISMATCH: {user_id}/{filename}")
                    errors += 1
            except Exception as e:
                print(f"  ERROR retrieving {user_id}/{filename}: {e}")
                errors += 1

    retrieve_elapsed = time.perf_counter() - retrieve_start

    print(f"  Retrieved {total_files} files in {retrieve_elapsed:.4f} seconds")
    print(f"  Errors: {errors}")

    # Demonstrate tamper detection: wrong passphrase
    print("\n--- Security Checks ---")
    try:
        storage.retrieve_file("alice", "report_q1.txt", "wrong-passphrase")
        print("  FAIL: Should have raised an error for wrong passphrase")
    except PermissionError as e:
        print(f"  PASS: Wrong passphrase detected — {e}")

    # Demonstrate missing file
    try:
        storage.retrieve_file("alice", "nonexistent.txt", "alice-strong-passphrase-2024!")
        print("  FAIL: Should have raised an error for missing file")
    except FileNotFoundError as e:
        print(f"  PASS: Missing file detected — {e}")

    # Demonstrate cross-user isolation
    try:
        storage.retrieve_file("bob", "report_q1.txt", "bob-secure-key-!@#$%")
        print("  FAIL: Should not find alice's file under bob")
    except FileNotFoundError as e:
        print(f"  PASS: Cross-user isolation — {e}")

    # Demonstrate tamper detection by corrupting stored ciphertext
    print("\n--- Tamper Detection ---")
    if "alice" in storage._storage and "notes.txt" in storage._storage["alice"]:
        salt, nonce, ciphertext, hmac_tag = storage._storage["alice"]["notes.txt"]
        # Flip a bit in the ciphertext
        corrupted = bytearray(ciphertext)
        corrupted[0] ^= 0xFF
        storage._storage["alice"]["notes.txt"] = (salt, nonce, bytes(corrupted), hmac_tag)
        try:
            storage.retrieve_file("alice", "notes.txt", "alice-strong-passphrase-2024!")
            print("  FAIL: Should have detected tampered ciphertext")
        except PermissionError as e:
            print(f"  PASS: Tampered ciphertext detected — {e}")

    # Summary
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  Total users:        {len(users)}")
    print(f"  Total files stored: {total_files}")
    print(f"  Store time:         {store_elapsed:.4f}s "
          f"({total_files / store_elapsed:.1f} files/sec)" if store_elapsed > 0 else "")
    print(f"  Retrieve time:      {retrieve_elapsed:.4f}s "
          f"({total_files / retrieve_elapsed:.1f} files/sec)" if retrieve_elapsed > 0 else "")
    print(f"  Integrity errors:   {errors}")
    print("=" * 70)


if __name__ == "__main__":
    main()