import os
import json
import time
import hmac
import base64
import hashlib
import secrets
import tempfile
from pathlib import Path
from typing import List


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _user_hash(self, user_id: str) -> str:
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()

    def _user_dir(self, user_id: str) -> Path:
        d = self.root / self._user_hash(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _file_id(self, filename: str) -> str:
        return hashlib.sha256(filename.encode("utf-8")).hexdigest()

    def _file_path(self, user_id: str, filename: str) -> Path:
        return self._user_dir(user_id) / f"{self._file_id(filename)}.json"

    def _derive_keys(self, passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
        master = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=64)
        return master[:32], master[32:]

    def _keystream(self, enc_key: bytes, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    def _encrypt(self, data: bytes, enc_key: bytes) -> tuple[bytes, bytes]:
        nonce = secrets.token_bytes(16)
        stream = self._keystream(enc_key, nonce, len(data))
        ciphertext = bytes(a ^ b for a, b in zip(data, stream))
        return nonce, ciphertext

    def _decrypt(self, ciphertext: bytes, nonce: bytes, enc_key: bytes) -> bytes:
        stream = self._keystream(enc_key, nonce, len(ciphertext))
        return bytes(a ^ b for a, b in zip(ciphertext, stream))

    def _atomic_write_json(self, path: Path, obj: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(obj, f, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        salt = secrets.token_bytes(16)
        enc_key, mac_key = self._derive_keys(passphrase, salt)
        plaintext = data.encode("utf-8")
        nonce, ciphertext = self._encrypt(plaintext, enc_key)

        meta = {
            "user_id": user_id,
            "filename": filename,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }

        mac_input = (
            meta["user_id"].encode("utf-8")
            + b"\x00"
            + meta["filename"].encode("utf-8")
            + b"\x00"
            + salt
            + nonce
            + ciphertext
        )
        tag = hmac.new(mac_key, mac_input, hashlib.sha256).digest()
        meta["tag"] = base64.b64encode(tag).decode("ascii")

        self._atomic_write_json(self._file_path(user_id, filename), meta)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        path = self._file_path(user_id, filename)
        if not path.exists():
            raise FileNotFoundError(f"File not found for user={user_id}, filename={filename}")

        with path.open("r", encoding="utf-8") as f:
            meta = json.load(f)

        salt = base64.b64decode(meta["salt"])
        nonce = base64.b64decode(meta["nonce"])
        ciphertext = base64.b64decode(meta["ciphertext"])
        stored_tag = base64.b64decode(meta["tag"])

        enc_key, mac_key = self._derive_keys(passphrase, salt)
        mac_input = (
            meta["user_id"].encode("utf-8")
            + b"\x00"
            + meta["filename"].encode("utf-8")
            + b"\x00"
            + salt
            + nonce
            + ciphertext
        )
        calc_tag = hmac.new(mac_key, mac_input, hashlib.sha256).digest()

        if not hmac.compare_digest(stored_tag, calc_tag):
            raise ValueError("Integrity check failed or incorrect passphrase")

        plaintext = self._decrypt(ciphertext, nonce, enc_key)
        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        result = []
        for p in user_dir.glob("*.json"):
            try:
                with p.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("user_id") == user_id and "filename" in meta:
                    result.append(meta["filename"])
            except Exception:
                continue
        result.sort()
        return result


def main() -> None:
    storage = SecureStorage("secure_storage_demo")

    demo_data = {
        "alice": {
            "passphrase": "alice-strong-passphrase",
            "files": {
                "notes.txt": "Alice private notes.",
                "report.md": "# Q4 Report\nRevenue increased by 12%.",
                "todo.txt": "1. Review contracts\n2. Update roadmap\n3. Call vendor",
            },
        },
        "bob": {
            "passphrase": "bob-super-secret",
            "files": {
                "resume.txt": "Bob Example\nSkills: Python, Security, Systems",
                "draft.doc": "Confidential draft content for Bob.",
                "data.csv": "id,value\n1,100\n2,200\n3,300",
                "large.txt": "X" * 200000,
            },
        },
    }

    start = time.perf_counter()
    total_files = 0

    for user_id, info in demo_data.items():
        passphrase = info["passphrase"]
        for filename, content in info["files"].items():
            storage.store_file(user_id, filename, content, passphrase)
            total_files += 1

    verified = 0
    for user_id, info in demo_data.items():
        passphrase = info["passphrase"]
        files = storage.list_files(user_id)
        for filename in files:
            content = storage.retrieve_file(user_id, filename, passphrase)
            if content == info["files"][filename]:
                verified += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage demonstration complete")
    print(f"Users: {len(demo_data)}")
    print(f"Files stored: {total_files}")
    print(f"Files verified: {verified}")
    for user_id in sorted(demo_data):
        print(f"{user_id}: {len(storage.list_files(user_id))} files -> {storage.list_files(user_id)}")
    print(f"Time taken: {elapsed:.6f} seconds")


if __name__ == "__main__":
    main()