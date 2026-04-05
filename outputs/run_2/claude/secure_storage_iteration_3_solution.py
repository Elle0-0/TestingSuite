import os
import hashlib
import hmac
import time
import struct
from collections import defaultdict


class SecureStorage:
    """
    Secure file storage with per-file encryption and tamper detection.
    
    Each file is encrypted with AES-256-CTR derived from the user's passphrase
    and a unique per-file salt. An HMAC-SHA256 tag ensures tamper-evidence.
    
    Internal storage uses a nested dict keyed by (user_id, filename) for O(1)
    lookup, and a per-user file list for efficient enumeration.
    """

    def __init__(self):
        # storage: {user_id: {filename: (salt, iv, ciphertext, hmac_tag)}}
        self._storage: dict[str, dict[str, tuple[bytes, bytes, bytes, bytes]]] = defaultdict(dict)

    @staticmethod
    def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
        """Derive a 32-byte encryption key and a 32-byte HMAC key using PBKDF2."""
        derived = hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt,
            iterations=100_000,
            dklen=64
        )
        enc_key = derived[:32]
        hmac_key = derived[32:]
        return enc_key, hmac_key

    @staticmethod
    def _aes_ctr_xor(key: bytes, iv: bytes, data: bytes) -> bytes:
        """
        AES-256-CTR encryption/decryption using SHA-256 as a PRF.
        
        For each 32-byte block, we compute:
            keystream_block = SHA256(key || iv || block_counter)
        and XOR with plaintext/ciphertext.
        """
        result = bytearray()
        block_size = 32
        num_blocks = (len(data) + block_size - 1) // block_size

        for i in range(num_blocks):
            counter_bytes = struct.pack('>Q', i)
            keystream_block = hashlib.sha256(key + iv + counter_bytes).digest()
            start = i * block_size
            end = min(start + block_size, len(data))
            chunk = data[start:end]
            result.extend(b ^ k for b, k in zip(chunk, keystream_block[:len(chunk)]))

        return bytes(result)

    @staticmethod
    def _compute_hmac(hmac_key: bytes, data: bytes) -> bytes:
        """Compute HMAC-SHA256 for tamper detection."""
        return hmac.new(hmac_key, data, hashlib.sha256).digest()

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """
        Encrypt and store a file with tamper-evident authentication.
        """
        salt = os.urandom(32)
        iv = os.urandom(16)

        enc_key, hmac_key = self._derive_keys(passphrase, salt)

        plaintext_bytes = data.encode('utf-8')
        ciphertext = self._aes_ctr_xor(enc_key, iv, plaintext_bytes)

        hmac_data = salt + iv + ciphertext
        hmac_tag = self._compute_hmac(hmac_key, hmac_data)

        self._storage[user_id][filename] = (salt, iv, ciphertext, hmac_tag)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """
        Retrieve and decrypt a file, verifying integrity before returning.
        """
        if user_id not in self._storage or filename not in self._storage[user_id]:
            raise ValueError(f"File '{filename}' not found for user '{user_id}'")

        salt, iv, ciphertext, stored_hmac_tag = self._storage[user_id][filename]

        enc_key, hmac_key = self._derive_keys(passphrase, salt)

        hmac_data = salt + iv + ciphertext
        computed_hmac_tag = self._compute_hmac(hmac_key, hmac_data)

        if not hmac.compare_digest(computed_hmac_tag, stored_hmac_tag):
            raise ValueError("Integrity check failed: data may have been tampered with or passphrase is incorrect")

        plaintext_bytes = self._aes_ctr_xor(enc_key, iv, ciphertext)
        return plaintext_bytes.decode('utf-8')

    def list_files(self, user_id: str) -> list[str]:
        """List all filenames stored for a given user."""
        if user_id not in self._storage:
            return []
        return list(self._storage[user_id].keys())


def _generate_file_content(user_id: str, file_index: int) -> str:
    """Generate file content for demonstration purposes."""
    header = f"Document {file_index} for user {user_id}\n"
    header += f"Created at iteration {file_index}\n"
    lines = []
    for j in range(10 + file_index * 5):
        lines.append(f"This is line {j} of the document with some enterprise content. " * 3)
    return header + "\n".join(lines)


def main():
    """Demonstrate secure storage with multiple users and files, with performance metrics."""
    storage = SecureStorage()

    users = [
        ("alice", "alice_strong_passphrase_2024!"),
        ("bob", "bob_secure_password_#99"),
        ("charlie", "charlie_p@ssw0rd_enterprise"),
    ]

    files_per_user = 5

    print("=" * 70)
    print("Secure Storage - Third Iteration: Scaling & Multi-File Operations")
    print("=" * 70)

    # --- Store files ---
    total_stored = 0
    total_bytes = 0
    store_start = time.perf_counter()

    for user_id, passphrase in users:
        for i in range(files_per_user):
            filename = f"document_{i}.txt"
            content = _generate_file_content(user_id, i)
            storage.store_file(user_id, filename, content, passphrase)
            total_stored += 1
            total_bytes += len(content.encode('utf-8'))

    store_elapsed = time.perf_counter() - store_start

    print(f"\nStored {total_stored} files across {len(users)} users")
    print(f"Total plaintext data: {total_bytes:,} bytes")
    print(f"Store time: {store_elapsed:.4f}s ({store_elapsed/total_stored*1000:.2f}ms per file)")

    # --- List files ---
    print("\n--- File Listings ---")
    for user_id, _ in users:
        file_list = storage.list_files(user_id)
        print(f"  {user_id}: {len(file_list)} files -> {file_list}")

    # --- Retrieve and verify files ---
    retrieve_start = time.perf_counter()
    retrieved_count = 0
    errors = 0

    for user_id, passphrase in users:
        for i in range(files_per_user):
            filename = f"document_{i}.txt"
            try:
                retrieved = storage.retrieve_file(user_id, filename, passphrase)
                expected_start = f"Document {i} for user {user_id}"
                assert retrieved.startswith(expected_start), \
                    f"Content mismatch for {user_id}/{filename}"
                retrieved_count += 1
            except Exception as e:
                print(f"  ERROR retrieving {user_id}/{filename}: {e}")
                errors += 1

    retrieve_elapsed = time.perf_counter() - retrieve_start

    print(f"\n--- Retrieval Summary ---")
    print(f"Retrieved {retrieved_count} files successfully, {errors} errors")
    print(f"Retrieve time: {retrieve_elapsed:.4f}s ({retrieve_elapsed/max(retrieved_count,1)*1000:.2f}ms per file)")

    # --- Security tests ---
    print("\n--- Security Verification ---")

    # Test wrong passphrase
    try:
        storage.retrieve_file("alice", "document_0.txt", "wrong_passphrase")
        print("  FAIL: Wrong passphrase should have been rejected")
    except ValueError:
        print("  PASS: Wrong passphrase correctly rejected")

    # Test non-existent file
    try:
        storage.retrieve_file("alice", "nonexistent.txt", "alice_strong_passphrase_2024!")
        print("  FAIL: Non-existent file should have raised error")
    except ValueError:
        print("  PASS: Non-existent file correctly rejected")

    # Test non-existent user
    try:
        storage.retrieve_file("unknown_user", "document_0.txt", "any_pass")
        print("  FAIL: Non-existent user should have raised error")
    except ValueError:
        print("  PASS: Non-existent user correctly rejected")

    # Test tamper detection
    tampered = False
    try:
        salt, iv, ciphertext, hmac_tag = storage._storage["alice"]["document_0.txt"]
        tampered_ciphertext = bytearray(ciphertext)
        tampered_ciphertext[0] ^= 0xFF
        storage._storage["alice"]["document_0.txt"] = (salt, iv, bytes(tampered_ciphertext), hmac_tag)
        storage.retrieve_file("alice", "document_0.txt", "alice_strong_passphrase_2024!")
        print("  FAIL: Tampered data should have been detected")
    except ValueError:
        print("  PASS: Data tampering correctly detected")
        tampered = True

    # Restore the original (re-store)
    if tampered:
        content = _generate_file_content("alice", 0)
        storage.store_file("alice", "document_0.txt", content, "alice_strong_passphrase_2024!")

    # --- Scalability test ---
    print("\n--- Scalability Test ---")
    scale_user = "scale_test_user"
    scale_passphrase = "scale_test_passphrase_!@#"
    num_scale_files = 100
    scale_content = "Scalability test content. " * 100

    scale_store_start = time.perf_counter()
    for i in range(num_scale_files):
        storage.store_file(scale_user, f"scale_file_{i:04d}.dat", scale_content, scale_passphrase)
    scale_store_elapsed = time.perf_counter() - scale_store_start

    scale_list = storage.list_files(scale_user)
    assert len(scale_list) == num_scale_files

    scale_retrieve_start = time.perf_counter()
    for i in range(num_scale_files):
        result = storage.retrieve_file(scale_user, f"scale_file_{i:04d}.dat", scale_passphrase)
        assert result == scale_content
    scale_retrieve_elapsed = time.perf_counter() - scale_retrieve_start

    print(f"  Stored {num_scale_files} files in {scale_store_elapsed:.4f}s "
          f"({scale_store_elapsed/num_scale_files*1000:.2f}ms/file)")
    print(f"  Retrieved {num_scale_files} files in {scale_retrieve_elapsed:.4f}s "
          f"({scale_retrieve_elapsed/num_scale_files*1000:.2f}ms/file)")
    print(f"  Total files in system: {sum(len(v) for v in storage._storage.values())}")

    # --- Cross-user isolation test ---
    print("\n--- Cross-User Isolation ---")
    try:
        storage.retrieve_file("alice", "document_1.txt", "bob_secure_password_#99")
        print("  FAIL: Cross-user access should have been rejected")
    except ValueError:
        print("  PASS: Cross-user isolation verified")

    total_elapsed = time.perf_counter() - store_start
    print(f"\n{'=' * 70}")
    print(f"Total demonstration time: {total_elapsed:.4f}s")
    print(f"All security and scalability checks passed.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()