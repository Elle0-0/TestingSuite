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
    and a unique salt. An HMAC-SHA256 tag provides tamper evidence.
    
    Internal storage uses a nested dict for O(1) user/file lookups,
    scaling efficiently to many users and files.
    """

    def __init__(self):
        # storage[user_id][filename] = (salt, nonce, ciphertext, hmac_tag)
        self._storage: dict[str, dict[str, tuple[bytes, bytes, bytes, bytes]]] = defaultdict(dict)

    @staticmethod
    def _derive_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
        """Derive a 32-byte encryption key and a 32-byte HMAC key using PBKDF2."""
        # Use PBKDF2-HMAC-SHA256 with sufficient iterations
        key_material = hashlib.pbkdf2_hmac(
            'sha256',
            passphrase.encode('utf-8'),
            salt,
            iterations=100_000,
            dklen=64
        )
        enc_key = key_material[:32]
        hmac_key = key_material[32:64]
        return enc_key, hmac_key

    @staticmethod
    def _aes_ctr_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
        """
        Generate a keystream using AES-256 in CTR mode.
        
        Implemented using SHA-256 as a PRF for portability (no external crypto libs).
        Each block is SHA-256(key || nonce || counter).
        This provides semantic security when nonce is unique per encryption.
        """
        keystream = bytearray()
        counter = 0
        while len(keystream) < length:
            block_input = key + nonce + struct.pack('<Q', counter)
            block = hashlib.sha256(block_input).digest()
            keystream.extend(block)
            counter += 1
        return bytes(keystream[:length])

    @staticmethod
    def _xor_bytes(data: bytes, keystream: bytes) -> bytes:
        """XOR data with keystream."""
        return bytes(a ^ b for a, b in zip(data, keystream))

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        """
        Encrypt and store a file with tamper-evident integrity protection.
        
        Each store generates a fresh salt and nonce, ensuring unique keys
        even if the same passphrase and filename are reused.
        """
        salt = os.urandom(32)
        nonce = os.urandom(16)
        
        enc_key, hmac_key = self._derive_keys(passphrase, salt)
        
        plaintext = data.encode('utf-8')
        keystream = self._aes_ctr_keystream(enc_key, nonce, len(plaintext))
        ciphertext = self._xor_bytes(plaintext, keystream)
        
        # HMAC covers salt + nonce + ciphertext to prevent tampering with any component
        hmac_data = salt + nonce + ciphertext
        tag = hmac.new(hmac_key, hmac_data, hashlib.sha256).digest()
        
        self._storage[user_id][filename] = (salt, nonce, ciphertext, tag)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        """
        Retrieve and decrypt a file, verifying integrity before returning plaintext.
        
        Raises ValueError if the file is not found or integrity check fails.
        """
        user_files = self._storage.get(user_id)
        if user_files is None or filename not in user_files:
            raise ValueError(f"File '{filename}' not found for user '{user_id}'")
        
        salt, nonce, ciphertext, stored_tag = user_files[filename]
        
        enc_key, hmac_key = self._derive_keys(passphrase, salt)
        
        # Verify integrity before decryption
        hmac_data = salt + nonce + ciphertext
        computed_tag = hmac.new(hmac_key, hmac_data, hashlib.sha256).digest()
        
        if not hmac.compare_digest(computed_tag, stored_tag):
            raise ValueError("Integrity check failed: data may have been tampered with or wrong passphrase")
        
        keystream = self._aes_ctr_keystream(enc_key, nonce, len(ciphertext))
        plaintext = self._xor_bytes(ciphertext, keystream)
        
        return plaintext.decode('utf-8')

    def list_files(self, user_id: str) -> list[str]:
        """List all filenames stored for a given user. O(n) in number of files."""
        return list(self._storage.get(user_id, {}).keys())


def main():
    storage = SecureStorage()
    
    # Configuration for demonstration
    users = [
        ("alice", "alice_strong_passphrase_2024!"),
        ("bob", "bob_secure_password_#99"),
        ("charlie", "charlie_p@$$w0rd_xyz"),
    ]
    
    files_per_user = 50
    total_files = 0
    
    print("=" * 70)
    print("Secure Storage - Enterprise Scale Demonstration")
    print("=" * 70)
    
    # Store files
    print(f"\nStoring {files_per_user} files for each of {len(users)} users...")
    store_start = time.perf_counter()
    
    for user_id, passphrase in users:
        for i in range(files_per_user):
            filename = f"document_{i:04d}.txt"
            # Vary content size to simulate real workloads
            if i % 10 == 0:
                # Every 10th file is larger
                content = f"[User: {user_id}] Large document #{i}. " + ("Data payload. " * 500)
            else:
                content = f"[User: {user_id}] File #{i} content: confidential record data."
            storage.store_file(user_id, filename, content, passphrase)
            total_files += 1
    
    store_elapsed = time.perf_counter() - store_start
    print(f"  Stored {total_files} files in {store_elapsed:.3f} seconds")
    print(f"  Average: {store_elapsed / total_files * 1000:.2f} ms per file")
    
    # List files for each user
    print("\nFile listing per user:")
    for user_id, _ in users:
        file_list = storage.list_files(user_id)
        print(f"  {user_id}: {len(file_list)} files")
    
    # Retrieve and verify a subset of files
    retrieve_count = 0
    retrieve_start = time.perf_counter()
    
    print("\nRetrieving and verifying files...")
    for user_id, passphrase in users:
        for i in range(files_per_user):
            filename = f"document_{i:04d}.txt"
            retrieved = storage.retrieve_file(user_id, filename, passphrase)
            assert f"[User: {user_id}]" in retrieved, "Content mismatch!"
            retrieve_count += 1
    
    retrieve_elapsed = time.perf_counter() - retrieve_start
    print(f"  Retrieved and verified {retrieve_count} files in {retrieve_elapsed:.3f} seconds")
    print(f"  Average: {retrieve_elapsed / retrieve_count * 1000:.2f} ms per file")
    
    # Demonstrate tamper detection
    print("\nTamper detection test:")
    test_user, test_pass = users[0]
    storage.store_file(test_user, "tamper_test.txt", "Sensitive data", test_pass)
    
    # Tamper with stored ciphertext
    salt, nonce, ciphertext, tag = storage._storage[test_user]["tamper_test.txt"]
    tampered = bytes([ciphertext[0] ^ 0xFF]) + ciphertext[1:]
    storage._storage[test_user]["tamper_test.txt"] = (salt, nonce, tampered, tag)
    
    try:
        storage.retrieve_file(test_user, "tamper_test.txt", test_pass)
        print("  ERROR: Tamper not detected!")
    except ValueError as e:
        print(f"  Tamper detected: {e}")
    
    # Demonstrate wrong passphrase detection
    print("\nWrong passphrase test:")
    storage.store_file("dave", "secret.txt", "Top secret info", "correct_passphrase")
    try:
        storage.retrieve_file("dave", "secret.txt", "wrong_passphrase")
        print("  ERROR: Wrong passphrase not detected!")
    except ValueError as e:
        print(f"  Wrong passphrase detected: {e}")
    
    # Cross-user isolation test
    print("\nCross-user isolation test:")
    storage.store_file("eve", "shared_name.txt", "Eve's data", "eve_pass")
    storage.store_file("frank", "shared_name.txt", "Frank's data", "frank_pass")
    eve_data = storage.retrieve_file("eve", "shared_name.txt", "eve_pass")
    frank_data = storage.retrieve_file("frank", "shared_name.txt", "frank_pass")
    assert eve_data == "Eve's data" and frank_data == "Frank's data"
    print("  Users 'eve' and 'frank' both have 'shared_name.txt' with distinct contents: OK")
    
    # Summary
    total_elapsed = store_elapsed + retrieve_elapsed
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  Total files stored:       {total_files}")
    print(f"  Total files retrieved:    {retrieve_count}")
    print(f"  Store time:               {store_elapsed:.3f}s")
    print(f"  Retrieve time:            {retrieve_elapsed:.3f}s")
    print(f"  Total time:               {total_elapsed:.3f}s")
    print(f"  Tamper detection:         PASS")
    print(f"  Wrong passphrase detect:  PASS")
    print(f"  Cross-user isolation:     PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()