import os
import json
import time
import base64
import hashlib
import hmac
from typing import List


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage_data"):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def _safe_name(self, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return digest

    def _user_dir(self, user_id: str) -> str:
        user_path = os.path.join(self.root_dir, self._safe_name(user_id))
        os.makedirs(user_path, exist_ok=True)
        return user_path

    def _file_path(self, user_id: str, filename: str) -> str:
        user_dir = self._user_dir(user_id)
        file_id = self._safe_name(filename)
        return os.path.join(user_dir, f"{file_id}.json")

    def _derive_keys(self, passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
        master = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            salt,
            200_000,
            dklen=64,
        )
        return master[:32], master[32:]

    def _xor_stream(self, data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
        output = bytearray()
        counter = 0
        offset = 0
        chunk_size = 32
        while offset < len(data):
            block = hashlib.sha256(
                enc_key + nonce + counter.to_bytes(8, "big")
            ).digest()
            take = min(chunk_size, len(data) - offset)
            for i in range(take):
                output.append(data[offset + i] ^ block[i])
            offset += take
            counter += 1
        return bytes(output)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        salt = os.urandom(16)
        nonce = os.urandom(16)
        enc_key, mac_key = self._derive_keys(passphrase, salt)

        plaintext = data.encode("utf-8")
        ciphertext = self._xor_stream(plaintext, enc_key, nonce)

        metadata = {
            "user_id_hash": self._safe_name(user_id),
            "filename": filename,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }

        mac_payload = (
            metadata["user_id_hash"].encode("utf-8")
            + b"|"
            + metadata["filename"].encode("utf-8")
            + b"|"
            + salt
            + b"|"
            + nonce
            + b"|"
            + ciphertext
        )
        tag = hmac.new(mac_key, mac_payload, hashlib.sha256).digest()
        metadata["tag"] = base64.b64encode(tag).decode("ascii")

        path = self._file_path(user_id, filename)
        temp_path = path + ".tmp"

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, separators=(",", ":"))

        os.replace(temp_path, path)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        path = self._file_path(user_id, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: user_id={user_id}, filename={filename}")

        with open(path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        salt = base64.b64decode(metadata["salt"])
        nonce = base64.b64decode(metadata["nonce"])
        ciphertext = base64.b64decode(metadata["ciphertext"])
        stored_tag = base64.b64decode(metadata["tag"])

        enc_key, mac_key = self._derive_keys(passphrase, salt)
        mac_payload = (
            metadata["user_id_hash"].encode("utf-8")
            + b"|"
            + metadata["filename"].encode("utf-8")
            + b"|"
            + salt
            + b"|"
            + nonce
            + b"|"
            + ciphertext
        )
        expected_tag = hmac.new(mac_key, mac_payload, hashlib.sha256).digest()

        if not hmac.compare_digest(stored_tag, expected_tag):
            raise ValueError("Integrity check failed or incorrect passphrase")

        plaintext = self._xor_stream(ciphertext, enc_key, nonce)
        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        files = []
        for entry in os.scandir(user_dir):
            if not entry.is_file() or not entry.name.endswith(".json"):
                continue
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                if metadata.get("user_id_hash") == self._safe_name(user_id):
                    files.append(metadata.get("filename", ""))
            except (OSError, json.JSONDecodeError):
                continue
        files.sort()
        return files


def main():
    storage = SecureStorage()

    dataset = {
        "alice": {
            "passphrase": "alice-strong-pass",
            "files": {
                "notes.txt": "Alice confidential notes.",
                "report.txt": "Quarterly report data for Alice.",
                "todo.md": "1. Review contracts\n2. Prepare presentation\n3. Call vendor",
            },
        },
        "bob": {
            "passphrase": "bob-strong-pass",
            "files": {
                "draft.txt": "Bob's first draft of the proposal.",
                "budget.csv": "item,cost\nservers,12000\nlicenses,4500\nsupport,2300",
                "archive.log": "2026-03-23 10:00:00 START\n2026-03-23 10:01:00 DONE",
            },
        },
        "carol": {
            "passphrase": "carol-strong-pass",
            "files": {
                "design.md": "# System Design\nScalable secure storage.",
                "meeting.txt": "Meeting notes: focus on scaling and integrity.",
            },
        },
    }

    start = time.perf_counter()
    total_stored = 0

    for user_id, info in dataset.items():
        for filename, content in info["files"].items():
            storage.store_file(user_id, filename, content, info["passphrase"])
            total_stored += 1

    retrieved_ok = 0
    for user_id, info in dataset.items():
        listed = storage.list_files(user_id)
        for filename in listed:
            content = storage.retrieve_file(user_id, filename, info["passphrase"])
            if content == info["files"][filename]:
                retrieved_ok += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage Demo Summary")
    print(f"Users: {len(dataset)}")
    print(f"Files stored: {total_stored}")
    print(f"Files retrieved successfully: {retrieved_ok}")
    for user_id in sorted(dataset):
        print(f"{user_id}: {len(storage.list_files(user_id))} files -> {storage.list_files(user_id)}")
    print(f"Time taken: {elapsed:.4f} seconds")


if __name__ == "__main__":
    main()