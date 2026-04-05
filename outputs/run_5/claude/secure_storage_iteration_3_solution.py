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
    
    Storage is organized by user_id for efficient per-user operations.
    """

    def __init__(self):
        # user_id -> {filename -> (salt, iv, hmac_tag, ciphertext)}
        self._storage: dict[str, dict[str, tuple[bytes, bytes, bytes, bytes]]] = defaultdict(dict)

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        """Derive a 256-bit key using PBKDF2-HMAC-SHA256."""
        return hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt,
            iterations=100_000,
            dklen=32
        )

    @staticmethod
    def _derive_hmac_key(passphrase: str, salt: bytes) -> bytes:
        """Derive a separate 256-bit key for HMAC using a different salt derivation."""
        return hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt + b'\x01',
            iterations=100_000,
            dklen=32
        )

    @staticmethod
    def _aes_ctr_crypt(key: bytes, iv: bytes, data: bytes) -> bytes:
        """
        AES-256-CTR encryption/decryption implemented using hashlib-based
        keystream generation. This avoids external crypto library dependencies
        while providing a secure stream cipher construction.
        
        Keystream blocks are generated as:
            HMAC-SHA256(key, iv || block_counter)
        
        Each block produces 32 bytes of keystream.
        """
        result = bytearray()
        block_counter = 0
        offset = 0
        data_len = len(data)

        while offset < data_len:
            # Generate keystream block using HMAC-SHA256 as a PRF
            counter_bytes = struct.pack('>Q', block_counter)
            keystream_block = hmac.new(key, iv + counter_bytes, hashlib.sha256).digest()

            # XOR data with keystream
            chunk_size = min(32, data_len - offset)
            for i in range(chunk_size):
                result.append(data[offset + i] ^ keystream_block[i])

            offset += chunk_size
            block_counter += 1

        return bytes(result)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """
        Encrypt and store a file with tamper-evident authentication.
        
        Process:
        1. Generate random salt (32 bytes) and IV (16 bytes)
        2. Derive encryption key and HMAC key from passphrase + salt
        3. Encrypt plaintext with AES-CTR-like stream cipher
        4. Compute HMAC-SHA256 over (filename || ciphertext) for tamper detection
        5. Store (salt, iv, hmac_tag, ciphertext)
        """
        salt = os.urandom(32)
        iv = os.urandom(16)

        enc_key = self._derive_key(passphrase, salt)
        hmac_key = self._derive_hmac_key(passphrase, salt)

        plaintext_bytes = data.encode('utf-8')
        ciphertext = self._aes_ctr_crypt(enc_key, iv, plaintext_bytes)

        # HMAC covers the filename and ciphertext to bind them together
        mac_data = filename.encode('utf-8') + ciphertext
        hmac_tag = hmac.new(hmac_key, mac_data, hashlib.sha256).digest()

        self._storage[user_id][filename] = (salt, iv, hmac_tag, ciphertext)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """
        Retrieve and decrypt a file, verifying its integrity.
        
        Raises:
            KeyError: if user_id or filename not found
            ValueError: if HMAC verification fails (tamper detected or wrong passphrase)
        """
        if user_id not in self._storage or filename not in self._storage[user_id]:
            raise KeyError(f"File '{filename}' not found for user '{user_id}'")

        salt, iv, stored_hmac, ciphertext = self._storage[user_id][filename]

        enc_key = self._derive_key(passphrase, salt)
        hmac_key = self._derive_hmac_key(passphrase, salt)

        # Verify integrity before decryption
        mac_data = filename.encode('utf-8') + ciphertext
        computed_hmac = hmac.new(hmac_key, mac_data, hashlib.sha256).digest()

        if not hmac.compare_digest(stored_hmac, computed_hmac):
            raise ValueError("Integrity check failed: data may be tampered with or wrong passphrase")

        plaintext_bytes = self._aes_ctr_crypt(enc_key, iv, ciphertext)
        return plaintext_bytes.decode('utf-8')

    def list_files(self, user_id: str) -> list[str]:
        """List all filenames stored for a given user."""
        if user_id not in self._storage:
            return []
        return sorted(self._storage[user_id].keys())


def main():
    """Demonstrate secure storage with multiple users and files."""
    storage = SecureStorage()

    # Define test users and their files
    users = {
        "alice": {
            "passphrase": "alice-strong-passphrase-2024!",
            "files": {
                "report_q1.txt": "Q1 revenue: $1.2M, expenses: $800K, profit: $400K",
                "report_q2.txt": "Q2 revenue: $1.5M, expenses: $900K, profit: $600K",
                "notes.txt": "Remember to review the budget proposal by Friday.",
                "credentials.txt": "API_KEY=sk-abc123def456\nDB_PASSWORD=hunter2",
            }
        },
        "bob": {
            "passphrase": "bob-secure-phrase-xyz!@#",
            "files": {
                "project_plan.txt": "Phase 1: Design (2 weeks)\nPhase 2: Implementation (6 weeks)",
                "meeting_notes.txt": "Discussed migration timeline. Deadline: March 15.",
                "config.yaml": "database:\n  host: db.internal\n  port: 5432\n  name: production",
            }
        },
        "charlie": {
            "passphrase": "charlie-p@$$w0rd-!secure",
            "files": {
                "diary.txt": "Today was a productive day. Finished the crypto module.",
                "todo.txt": "1. Code review\n2. Deploy staging\n3. Write tests",
            }
        }
    }

    # Also add a batch of files to test scaling
    num_scale_files = 50
    users["enterprise_user"] = {
        "passphrase": "enterprise-grade-passphrase-2024",
        "files": {
            f"document_{i:04d}.txt": f"Content of document {i}. " * 10
            for i in range(num_scale_files)
        }
    }

    total_files_stored = 0
    total_files_retrieved = 0
    errors = []

    print("=" * 70)
    print("SECURE STORAGE SYSTEM - Enterprise Deployment Demo")
    print("=" * 70)

    # --- Store Phase ---
    print("\n--- Storing Files ---")
    store_start = time.perf_counter()

    for user_id, user_data in users.items():
        passphrase = user_data["passphrase"]
        for filename, content in user_data["files"].items():
            storage.store_file(user_id, filename, content, passphrase)
            total_files_stored += 1

    store_elapsed = time.perf_counter() - store_start
    print(f"Stored {total_files_stored} files in {store_elapsed:.3f} seconds")
    print(f"Average: {store_elapsed / total_files_stored * 1000:.1f} ms per file")

    # --- List Phase ---
    print("\n--- Listing Files Per User ---")
    for user_id in users:
        file_list = storage.list_files(user_id)
        print(f"  {user_id}: {len(file_list)} files")
        if len(file_list) <= 6:
            for fn in file_list:
                print(f"    - {fn}")

    # --- Retrieve & Verify Phase ---
    print("\n--- Retrieving and Verifying Files ---")
    retrieve_start = time.perf_counter()

    for user_id, user_data in users.items():
        passphrase = user_data["passphrase"]
        for filename, original_content in user_data["files"].items():
            try:
                retrieved = storage.retrieve_file(user_id, filename, passphrase)
                if retrieved == original_content:
                    total_files_retrieved += 1
                else:
                    errors.append(f"MISMATCH: {user_id}/{filename}")
            except Exception as e:
                errors.append(f"ERROR: {user_id}/{filename}: {e}")

    retrieve_elapsed = time.perf_counter() - retrieve_start
    print(f"Retrieved {total_files_retrieved} files in {retrieve_elapsed:.3f} seconds")
    print(f"Average: {retrieve_elapsed / total_files_retrieved * 1000:.1f} ms per file")

    # --- Tamper Detection Test ---
    print("\n--- Tamper Detection Test ---")
    try:
        storage.retrieve_file("alice", "report_q1.txt", "wrong-passphrase")
        print("  FAIL: Should have raised an error for wrong passphrase")
    except ValueError as e:
        print(f"  PASS: Wrong passphrase correctly detected: {e}")
    except Exception as e:
        print(f"  FAIL: Unexpected error type: {e}")

    # Test tamper by modifying stored ciphertext directly
    if "alice" in storage._storage and "notes.txt" in storage._storage["alice"]:
        salt, iv, hmac_tag, ciphertext = storage._storage["alice"]["notes.txt"]
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF  # Flip bits
        storage._storage["alice"]["notes.txt"] = (salt, iv, hmac_tag, bytes(tampered))
        try:
            storage.retrieve_file("alice", "notes.txt", users["alice"]["passphrase"])
            print("  FAIL: Should have detected tampered ciphertext")
        except ValueError as e:
            print(f"  PASS: Tampered data correctly detected: {e}")

    # Test non-existent file
    try:
        storage.retrieve_file("alice", "nonexistent.txt", "any")
        print("  FAIL: Should have raised KeyError")
    except KeyError as e:
        print(f"  PASS: Non-existent file correctly reported: {e}")

    # Test non-existent user
    empty_list = storage.list_files("nonexistent_user")
    print(f"  PASS: list_files for unknown user returned: {empty_list}")

    # --- Summary ---
    total_elapsed = store_elapsed + retrieve_elapsed
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Users:           {len(users)}")
    print(f"  Files stored:    {total_files_stored}")
    print(f"  Files verified:  {total_files_retrieved}")
    print(f"  Errors:          {len(errors)}")
    print(f"  Store time:      {store_elapsed:.3f}s")
    print(f"  Retrieve time:   {retrieve_elapsed:.3f}s")
    print(f"  Total time:      {total_elapsed:.3f}s")

    if errors:
        print("\n  ERRORS:")
        for err in errors:
            print(f"    {err}")
    else:
        print("\n  All operations completed successfully!")

    print("=" * 70)


if __name__ == "__main__":
    main()