import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import List


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_name = "index.json"

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        filename_key = self._safe_name(filename)
        file_path = user_dir / f"{filename_key}.blob"

        plaintext = data.encode("utf-8")
        salt = secrets.token_bytes(16)
        enc_key, mac_key = self._derive_keys(passphrase, salt)
        nonce = secrets.token_bytes(32)
        ciphertext = self._xor_stream_encrypt(plaintext, enc_key, nonce)

        header = {
            "version": 1,
            "filename": filename,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "length": len(plaintext),
        }
        header_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
        tag = hmac.new(mac_key, header_bytes + ciphertext, hashlib.sha256).digest()

        payload = (
            len(header_bytes).to_bytes(8, "big")
            + header_bytes
            + ciphertext
            + tag
        )

        self._atomic_write(file_path, payload)
        self._update_index(user_dir, filename, filename_key)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        user_dir = self._user_dir(user_id)
        index = self._load_index(user_dir)
        if filename not in index:
            raise FileNotFoundError(f"File not found: {filename}")

        filename_key = index[filename]
        file_path = user_dir / f"{filename_key}.blob"
        if not file_path.exists():
            raise FileNotFoundError(f"Stored blob missing for: {filename}")

        blob = file_path.read_bytes()
        if len(blob) < 8 + 32:
            raise ValueError("Corrupted file format")

        header_len = int.from_bytes(blob[:8], "big")
        if len(blob) < 8 + header_len + 32:
            raise ValueError("Corrupted file format")

        header_bytes = blob[8:8 + header_len]
        tag = blob[-32:]
        ciphertext = blob[8 + header_len:-32]

        try:
            header = json.loads(header_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError("Invalid file header") from e

        if header.get("filename") != filename:
            raise ValueError("Filename mismatch in stored data")

        salt = base64.b64decode(header["salt"])
        nonce = base64.b64decode(header["nonce"])
        expected_length = int(header["length"])

        enc_key, mac_key = self._derive_keys(passphrase, salt)
        expected_tag = hmac.new(mac_key, header_bytes + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Authentication failed: wrong passphrase or tampered file")

        plaintext = self._xor_stream_encrypt(ciphertext, enc_key, nonce)
        if len(plaintext) != expected_length:
            raise ValueError("Length mismatch after decryption")

        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        index = self._load_index(user_dir)
        return sorted(index.keys())

    def _user_dir(self, user_id: str) -> Path:
        return self.root / self._safe_name(user_id)

    def _safe_name(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _derive_keys(self, passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
        master = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=64)
        return master[:32], master[32:]

    def _keystream_block(self, key: bytes, nonce: bytes, counter: int) -> bytes:
        return hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()

    def _xor_stream_encrypt(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        out = bytearray(len(data))
        offset = 0
        counter = 0
        while offset < len(data):
            block = self._keystream_block(key, nonce, counter)
            chunk = data[offset:offset + len(block)]
            for i, b in enumerate(chunk):
                out[offset + i] = b ^ block[i]
            offset += len(chunk)
            counter += 1
        return bytes(out)

    def _atomic_write(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_name = tmp.name
        os.replace(temp_name, path)

    def _load_index(self, user_dir: Path) -> dict:
        index_path = user_dir / self._index_name
        if not index_path.exists():
            return {}
        try:
            with index_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return {str(k): str(v) for k, v in data.items()}
        except Exception:
            return {}

    def _update_index(self, user_dir: Path, filename: str, filename_key: str) -> None:
        index = self._load_index(user_dir)
        index[filename] = filename_key
        index_bytes = json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self._atomic_write(user_dir / self._index_name, index_bytes)


def main() -> None:
    storage = SecureStorage()
    users = {
        "alice": {
            "passphrase": "alice-strong-passphrase",
            "files": {
                "notes.txt": "Alice meeting notes\n" * 200,
                "report.md": "# Quarterly Report\n" + ("Revenue stable.\n" * 500),
                "archive.log": ("event=ok\n" * 2000),
            },
        },
        "bob": {
            "passphrase": "bob-unique-passphrase",
            "files": {
                "tasks.json": json.dumps({"tasks": [f"task-{i}" for i in range(200)]}),
                "draft.txt": "Bob draft content\n" * 1000,
            },
        },
        "carol": {
            "passphrase": "carol-secure-passphrase",
            "files": {
                "design.txt": "System design details\n" * 1500,
                "readme.txt": "Readme\n" * 300,
                "data.csv": "\n".join(f"{i},{i*i},{i*i*i}" for i in range(1000)),
            },
        },
    }

    start = time.perf_counter()
    stored_count = 0

    for user_id, info in users.items():
        passphrase = info["passphrase"]
        for filename, content in info["files"].items():
            storage.store_file(user_id, filename, content, passphrase)
            stored_count += 1

    retrieved_ok = 0
    for user_id, info in users.items():
        passphrase = info["passphrase"]
        files = storage.list_files(user_id)
        for filename in files:
            content = storage.retrieve_file(user_id, filename, passphrase)
            if content == info["files"][filename]:
                retrieved_ok += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage demonstration complete")
    print(f"Users: {len(users)}")
    print(f"Files stored: {stored_count}")
    print(f"Files verified: {retrieved_ok}")
    for user_id in sorted(users):
        print(f"{user_id}: {len(storage.list_files(user_id))} files -> {storage.list_files(user_id)}")
    print(f"Time taken: {elapsed:.6f} seconds")


if __name__ == "__main__":
    main()