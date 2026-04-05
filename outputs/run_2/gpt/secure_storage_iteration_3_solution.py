import os
import json
import time
import hmac
import base64
import hashlib
import tempfile
from typing import List, Dict

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_AESGCM = True
except Exception:
    _HAS_AESGCM = False


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage_data"):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        self._validate_name(user_id, "user_id")
        self._validate_name(filename, "filename")
        user_dir = self._user_dir(user_id)
        os.makedirs(user_dir, exist_ok=True)

        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        nonce = os.urandom(12)
        plaintext = data.encode("utf-8")
        aad = self._aad(user_id, filename)

        if _HAS_AESGCM:
            ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
            payload = {
                "v": 1,
                "alg": "AES-256-GCM",
                "kdf": "PBKDF2-HMAC-SHA256",
                "iter": 200_000,
                "salt": self._b64e(salt),
                "nonce": self._b64e(nonce),
                "ct": self._b64e(ciphertext),
            }
        else:
            enc_key, mac_key = self._split_key_material(key)
            keystream = self._xor_stream(enc_key, nonce, len(plaintext))
            ciphertext = bytes(a ^ b for a, b in zip(plaintext, keystream))
            tag = hmac.new(mac_key, aad + nonce + ciphertext, hashlib.sha256).digest()
            payload = {
                "v": 1,
                "alg": "XOR-HMAC-SHA256",
                "kdf": "PBKDF2-HMAC-SHA256",
                "iter": 200_000,
                "salt": self._b64e(salt),
                "nonce": self._b64e(nonce),
                "ct": self._b64e(ciphertext),
                "tag": self._b64e(tag),
            }

        path = self._file_path(user_id, filename)
        self._atomic_write_json(path, payload)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        self._validate_name(user_id, "user_id")
        self._validate_name(filename, "filename")
        path = self._file_path(user_id, filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"File not found for user '{user_id}': {filename}")

        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        salt = self._b64d(payload["salt"])
        nonce = self._b64d(payload["nonce"])
        ciphertext = self._b64d(payload["ct"])
        key = self._derive_key(passphrase, salt)
        aad = self._aad(user_id, filename)

        alg = payload.get("alg")
        if alg == "AES-256-GCM":
            if not _HAS_AESGCM:
                raise RuntimeError("AES-GCM encrypted file cannot be decrypted: cryptography package unavailable")
            try:
                plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
            except Exception as e:
                raise ValueError("Invalid passphrase or data integrity check failed") from e
        elif alg == "XOR-HMAC-SHA256":
            tag = self._b64d(payload["tag"])
            enc_key, mac_key = self._split_key_material(key)
            expected_tag = hmac.new(mac_key, aad + nonce + ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(tag, expected_tag):
                raise ValueError("Invalid passphrase or data integrity check failed")
            keystream = self._xor_stream(enc_key, nonce, len(ciphertext))
            plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))
        else:
            raise ValueError("Unsupported encryption algorithm")

        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        self._validate_name(user_id, "user_id")
        user_dir = self._user_dir(user_id)
        if not os.path.isdir(user_dir):
            return []
        names = []
        for entry in os.scandir(user_dir):
            if entry.is_file() and entry.name.endswith(".json"):
                names.append(entry.name[:-5])
        names.sort()
        return names

    def _user_dir(self, user_id: str) -> str:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return os.path.join(self.root_dir, digest[:2], digest[2:4], digest)

    def _file_path(self, user_id: str, filename: str) -> str:
        file_id = hashlib.sha256(filename.encode("utf-8")).hexdigest()
        return os.path.join(self._user_dir(user_id), f"{file_id}.json")

    def _aad(self, user_id: str, filename: str) -> bytes:
        return f"{user_id}\0{filename}".encode("utf-8")

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            salt,
            200_000,
            dklen=32,
        )

    def _split_key_material(self, key: bytes):
        enc_key = hashlib.sha256(key + b":enc").digest()
        mac_key = hashlib.sha256(key + b":mac").digest()
        return enc_key, mac_key

    def _xor_stream(self, key: bytes, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    def _atomic_write_json(self, path: str, payload: Dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(payload, tmp_file, separators=(",", ":"))
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _b64e(self, b: bytes) -> str:
        return base64.b64encode(b).decode("ascii")

    def _b64d(self, s: str) -> bytes:
        return base64.b64decode(s.encode("ascii"))

    def _validate_name(self, value: str, field: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} must be a non-empty string")


def main():
    storage = SecureStorage()
    samples = {
        "alice": [
            ("notes.txt", "Quarterly planning notes and action items.", "alice-pass"),
            ("todo.md", "# TODO\n- Review budget\n- Sync with engineering", "alice-pass"),
            ("report.json", '{"status":"ok","items":[1,2,3,4]}', "alice-pass"),
        ],
        "bob": [
            ("draft.txt", "This is a confidential draft for client review.", "bob-pass"),
            ("data.csv", "id,value\n1,100\n2,200\n3,300", "bob-pass"),
        ],
        "carol": [
            ("design.txt", "System design v3 with scaling considerations.", "carol-pass"),
            ("archive.log", "entry1\nentry2\nentry3\nentry4", "carol-pass"),
            ("readme.md", "Internal readme for secure storage usage.", "carol-pass"),
            ("large.txt", "A" * 100000, "carol-pass"),
        ],
    }

    start = time.perf_counter()
    stored_count = 0
    for user_id, files in samples.items():
        for filename, data, passphrase in files:
            storage.store_file(user_id, filename, data, passphrase)
            stored_count += 1

    verified_count = 0
    for user_id, files in samples.items():
        listed = storage.list_files(user_id)
        expected_hash_names = sorted(hashlib.sha256(name.encode("utf-8")).hexdigest() for name, _, _ in files)
        if listed != expected_hash_names:
            raise AssertionError(f"List mismatch for {user_id}")
        for filename, data, passphrase in files:
            recovered = storage.retrieve_file(user_id, filename, passphrase)
            if recovered != data:
                raise AssertionError(f"Data mismatch for {user_id}/{filename}")
            verified_count += 1

    elapsed = time.perf_counter() - start
    print(f"users={len(samples)} files_stored={stored_count} files_verified={verified_count} time_seconds={elapsed:.4f}")


if __name__ == "__main__":
    main()