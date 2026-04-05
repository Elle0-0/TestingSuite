import os
import json
import time
import hmac
import base64
import hashlib
import tempfile
from typing import List


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage"):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)
        self._pbkdf2_iterations = 200_000
        self._chunk_size = 64 * 1024

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id must be a non-empty string")
        if not isinstance(filename, str) or not filename:
            raise ValueError("filename must be a non-empty string")
        if not isinstance(data, str):
            raise ValueError("data must be a string")
        if not isinstance(passphrase, str) or not passphrase:
            raise ValueError("passphrase must be a non-empty string")

        user_dir = self._user_dir(user_id)
        os.makedirs(user_dir, exist_ok=True)

        safe_name = self._safe_filename(filename)
        file_path = os.path.join(user_dir, safe_name + ".json")

        salt = os.urandom(16)
        enc_key, mac_key = self._derive_keys(passphrase, salt)
        plaintext = data.encode("utf-8")

        nonce = os.urandom(16)
        keystream = self._keystream(enc_key, nonce, len(plaintext))
        ciphertext = self._xor_bytes(plaintext, keystream)

        mac = hmac.new(mac_key, digestmod=hashlib.sha256)
        mac.update(user_id.encode("utf-8"))
        mac.update(b"\x00")
        mac.update(filename.encode("utf-8"))
        mac.update(b"\x00")
        mac.update(nonce)
        mac.update(ciphertext)
        tag = mac.digest()

        payload = {
            "version": 1,
            "user_id": user_id,
            "filename": filename,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "tag": base64.b64encode(tag).decode("ascii"),
        }

        self._atomic_write_json(file_path, payload)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id must be a non-empty string")
        if not isinstance(filename, str) or not filename:
            raise ValueError("filename must be a non-empty string")
        if not isinstance(passphrase, str) or not passphrase:
            raise ValueError("passphrase must be a non-empty string")

        file_path = os.path.join(self._user_dir(user_id), self._safe_filename(filename) + ".json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found for user={user_id}, filename={filename}")

        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        try:
            salt = base64.b64decode(payload["salt"])
            nonce = base64.b64decode(payload["nonce"])
            ciphertext = base64.b64decode(payload["ciphertext"])
            stored_tag = base64.b64decode(payload["tag"])
            stored_user_id = payload["user_id"]
            stored_filename = payload["filename"]
        except Exception as e:
            raise ValueError("Stored file format is invalid") from e

        enc_key, mac_key = self._derive_keys(passphrase, salt)

        mac = hmac.new(mac_key, digestmod=hashlib.sha256)
        mac.update(stored_user_id.encode("utf-8"))
        mac.update(b"\x00")
        mac.update(stored_filename.encode("utf-8"))
        mac.update(b"\x00")
        mac.update(nonce)
        mac.update(ciphertext)
        expected_tag = mac.digest()

        if not hmac.compare_digest(stored_tag, expected_tag):
            raise ValueError("Integrity check failed or incorrect passphrase")

        keystream = self._keystream(enc_key, nonce, len(ciphertext))
        plaintext = self._xor_bytes(ciphertext, keystream)

        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError("Decryption failed") from e

    def list_files(self, user_id: str) -> List[str]:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id must be a non-empty string")

        user_dir = self._user_dir(user_id)
        if not os.path.isdir(user_dir):
            return []

        names = []
        for entry in os.scandir(user_dir):
            if entry.is_file() and entry.name.endswith(".json"):
                try:
                    with open(entry.path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    filename = payload.get("filename")
                    if isinstance(filename, str):
                        names.append(filename)
                except Exception:
                    continue
        names.sort()
        return names

    def _user_dir(self, user_id: str) -> str:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return os.path.join(self.root_dir, digest[:2], digest[2:4], digest)

    def _safe_filename(self, filename: str) -> str:
        digest = hashlib.sha256(filename.encode("utf-8")).hexdigest()
        return digest

    def _derive_keys(self, passphrase: str, salt: bytes):
        master = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            salt,
            self._pbkdf2_iterations,
            dklen=64,
        )
        return master[:32], master[32:]

    def _keystream(self, key: bytes, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    def _xor_bytes(self, a: bytes, b: bytes) -> bytes:
        return bytes(x ^ y for x, y in zip(a, b))

    def _atomic_write_json(self, path: str, payload: dict) -> None:
        directory = os.path.dirname(path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, separators=(",", ":"))
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise


def main():
    storage = SecureStorage()

    users = {
        "alice": {
            "passphrase": "alice-secret-pass",
            "files": {
                "notes.txt": "Alice notes: quarterly planning, budgets, roadmap.",
                "report.md": "# Alice Report\nEverything is on track.\n",
                "large.txt": "A" * 200000,
            },
        },
        "bob": {
            "passphrase": "bob-strong-pass",
            "files": {
                "todo.txt": "Buy milk\nReview contracts\nSchedule meeting",
                "design.txt": "System design draft v2 with scaling considerations.",
                "archive.log": "entry\n" * 50000,
            },
        },
        "carol": {
            "passphrase": "carol-safe-pass",
            "files": {
                "memo.txt": "Confidential memo for Carol.",
                "ideas.txt": "Feature A\nFeature B\nFeature C",
            },
        },
    }

    start = time.perf_counter()
    stored_count = 0

    for user_id, info in users.items():
        for filename, content in info["files"].items():
            storage.store_file(user_id, filename, content, info["passphrase"])
            stored_count += 1

    retrieved_ok = 0
    for user_id, info in users.items():
        listed = storage.list_files(user_id)
        for filename in listed:
            content = storage.retrieve_file(user_id, filename, info["passphrase"])
            if content == info["files"][filename]:
                retrieved_ok += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage demo summary")
    print(f"Users: {len(users)}")
    print(f"Files stored: {stored_count}")
    print(f"Files retrieved and verified: {retrieved_ok}")
    print(f"Time taken: {elapsed:.4f} seconds")

    for user_id in sorted(users):
        print(f"{user_id}: {len(storage.list_files(user_id))} files -> {storage.list_files(user_id)}")


if __name__ == "__main__":
    main()