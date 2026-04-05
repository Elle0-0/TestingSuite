import os
import json
import time
import hmac
import base64
import hashlib
import tempfile
from typing import List


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage_data") -> None:
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._user_dir(user_id)
        os.makedirs(user_dir, exist_ok=True)

        salt = os.urandom(16)
        enc_key, mac_key = self._derive_keys(passphrase, salt)
        plaintext = data.encode("utf-8")
        nonce = os.urandom(16)
        ciphertext = self._xor_stream_encrypt(plaintext, enc_key, nonce)
        mac = self._compute_mac(user_id, filename, salt, nonce, ciphertext, mac_key)

        record = {
            "v": 1,
            "user_id": user_id,
            "filename": filename,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "mac": base64.b64encode(mac).decode("ascii"),
        }

        path = self._file_path(user_id, filename)
        self._atomic_write_json(path, record)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        path = self._file_path(user_id, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found for user '{user_id}': {filename}")

        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)

        salt = base64.b64decode(record["salt"])
        nonce = base64.b64decode(record["nonce"])
        ciphertext = base64.b64decode(record["ciphertext"])
        stored_mac = base64.b64decode(record["mac"])

        enc_key, mac_key = self._derive_keys(passphrase, salt)
        expected_mac = self._compute_mac(
            record["user_id"],
            record["filename"],
            salt,
            nonce,
            ciphertext,
            mac_key,
        )

        if not hmac.compare_digest(stored_mac, expected_mac):
            raise ValueError("Integrity check failed or incorrect passphrase")

        plaintext = self._xor_stream_encrypt(ciphertext, enc_key, nonce)
        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        if not os.path.isdir(user_dir):
            return []

        result = []
        for entry in os.scandir(user_dir):
            if entry.is_file() and entry.name.endswith(".json"):
                safe_name = entry.name[:-5]
                result.append(self._unsanitize_filename(safe_name))
        result.sort()
        return result

    def _user_dir(self, user_id: str) -> str:
        safe_user = self._safe_component(user_id)
        return os.path.join(self.root_dir, safe_user)

    def _file_path(self, user_id: str, filename: str) -> str:
        return os.path.join(self._user_dir(user_id), self._sanitize_filename(filename) + ".json")

    def _safe_component(self, value: str) -> str:
        encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")
        return encoded.rstrip("=")

    def _sanitize_filename(self, filename: str) -> str:
        encoded = base64.urlsafe_b64encode(filename.encode("utf-8")).decode("ascii")
        return encoded.rstrip("=")

    def _unsanitize_filename(self, safe_name: str) -> str:
        padding = "=" * (-len(safe_name) % 4)
        return base64.urlsafe_b64decode((safe_name + padding).encode("ascii")).decode("utf-8")

    def _derive_keys(self, passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
        master = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=64)
        return master[:32], master[32:]

    def _compute_mac(
        self,
        user_id: str,
        filename: str,
        salt: bytes,
        nonce: bytes,
        ciphertext: bytes,
        mac_key: bytes,
    ) -> bytes:
        mac_input = (
            b"v1|"
            + user_id.encode("utf-8")
            + b"|"
            + filename.encode("utf-8")
            + b"|"
            + salt
            + b"|"
            + nonce
            + b"|"
            + ciphertext
        )
        return hmac.new(mac_key, mac_input, hashlib.sha256).digest()

    def _xor_stream_encrypt(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        out = bytearray(len(data))
        counter = 0
        offset = 0
        while offset < len(data):
            block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
            n = min(len(block), len(data) - offset)
            for i in range(n):
                out[offset + i] = data[offset + i] ^ block[i]
            offset += n
            counter += 1
        return bytes(out)

    def _atomic_write_json(self, path: str, obj: dict) -> None:
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(obj, tmp_file, ensure_ascii=False, separators=(",", ":"))
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            finally:
                raise


def main() -> None:
    storage = SecureStorage()

    demo_data = {
        "alice": [
            ("notes.txt", "Project notes for Q1.\nAction items:\n- Review budget\n- Finalize roadmap", "alpha-pass"),
            ("report.md", "# Weekly Report\nProgress is on track.\nRisks are low.", "alpha-pass"),
            ("archive.log", "2026-03-18 10:00:00 INFO Started\n" * 200, "alpha-pass"),
        ],
        "bob": [
            ("todo.txt", "Buy milk\nCall supplier\nPrepare invoice", "beta-pass"),
            ("design.txt", "System design draft:\n- API gateway\n- Auth service\n- Storage layer", "beta-pass"),
            ("large.txt", "X" * 100000, "beta-pass"),
        ],
        "carol": [
            ("personal.txt", "Private reflections and reminders.", "gamma-pass"),
            ("plans.csv", "month,goal\nApril,Launch MVP\nMay,Collect feedback", "gamma-pass"),
        ],
    }

    start = time.perf_counter()
    stored_count = 0

    for user_id, files in demo_data.items():
        for filename, data, passphrase in files:
            storage.store_file(user_id, filename, data, passphrase)
            stored_count += 1

    retrieved_ok = 0
    for user_id, files in demo_data.items():
        listed = storage.list_files(user_id)
        expected = sorted([name for name, _, _ in files])
        if listed != expected:
            raise AssertionError(f"List mismatch for {user_id}: {listed} != {expected}")

        for filename, original_data, passphrase in files:
            recovered = storage.retrieve_file(user_id, filename, passphrase)
            if recovered != original_data:
                raise AssertionError(f"Recovered data mismatch for {user_id}/{filename}")
            retrieved_ok += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage demonstration complete")
    print(f"Users: {len(demo_data)}")
    print(f"Files stored: {stored_count}")
    print(f"Files retrieved and verified: {retrieved_ok}")
    print(f"Time taken: {elapsed:.4f} seconds")
    for user_id in sorted(demo_data):
        print(f"{user_id}: {len(storage.list_files(user_id))} files -> {storage.list_files(user_id)}")


if __name__ == "__main__":
    main()