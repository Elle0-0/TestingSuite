import os
import json
import time
import base64
import hashlib
import hmac
import secrets
from pathlib import Path
from typing import List

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as e:
    raise RuntimeError("This solution requires the 'cryptography' package to be installed.") from e


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage_data") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._users_dir = self.root / "users"
        self._users_dir.mkdir(parents=True, exist_ok=True)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        file_id = self._file_id(filename)
        payload_path = user_dir / f"{file_id}.bin"
        meta_path = user_dir / f"{file_id}.json"

        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        key = self._derive_key(passphrase, salt)

        data_bytes = data.encode("utf-8")
        aad = self._aad(user_id, filename)
        ciphertext = AESGCM(key).encrypt(nonce, data_bytes, aad)

        temp_payload = payload_path.with_suffix(".bin.tmp")
        temp_meta = meta_path.with_suffix(".json.tmp")

        with open(temp_payload, "wb") as f:
            f.write(ciphertext)

        metadata = {
            "user_id": user_id,
            "filename": filename,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "version": 1,
            "algo": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA256",
            "iterations": 200_000,
            "size": len(data_bytes),
            "sha256": hashlib.sha256(data_bytes).hexdigest(),
        }

        with open(temp_meta, "w", encoding="utf-8") as f:
            json.dump(metadata, f, separators=(",", ":"))

        os.replace(temp_payload, payload_path)
        os.replace(temp_meta, meta_path)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        user_dir = self._user_dir(user_id)
        file_id = self._file_id(filename)
        payload_path = user_dir / f"{file_id}.bin"
        meta_path = user_dir / f"{file_id}.json"

        if not payload_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"File not found for user_id={user_id!r}, filename={filename!r}")

        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        if metadata.get("user_id") != user_id or metadata.get("filename") != filename:
            raise ValueError("Metadata mismatch detected")

        salt = base64.b64decode(metadata["salt"])
        nonce = base64.b64decode(metadata["nonce"])
        key = self._derive_key(passphrase, salt)

        with open(payload_path, "rb") as f:
            ciphertext = f.read()

        aad = self._aad(user_id, filename)
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ValueError("Authentication failed or incorrect passphrase") from e

        expected_hash = metadata.get("sha256")
        actual_hash = hashlib.sha256(plaintext).hexdigest()
        if expected_hash and not hmac.compare_digest(expected_hash, actual_hash):
            raise ValueError("Integrity check failed")

        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []

        files = []
        for meta_path in user_dir.glob("*.json"):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                if metadata.get("user_id") == user_id and "filename" in metadata:
                    files.append(metadata["filename"])
            except Exception:
                continue
        files.sort()
        return files

    def _user_dir(self, user_id: str) -> Path:
        user_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return self._users_dir / user_hash[:2] / user_hash

    @staticmethod
    def _file_id(filename: str) -> str:
        return hashlib.sha256(filename.encode("utf-8")).hexdigest()

    @staticmethod
    def _aad(user_id: str, filename: str) -> bytes:
        return f"{user_id}\0{filename}".encode("utf-8")

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            salt,
            200_000,
            dklen=32,
        )


def main() -> None:
    storage = SecureStorage()

    users = {
        "alice": {
            "passphrase": "alice-strong-passphrase",
            "files": {
                "notes.txt": "Alice private notes.\nLine 2.\nLine 3.",
                "project.md": "# Project\nConfidential project details for Alice.",
                "large.txt": "A" * 200_000,
            },
        },
        "bob": {
            "passphrase": "bob-secure-passphrase",
            "files": {
                "todo.txt": "Buy milk\nFinish report\nCall team",
                "design.json": json.dumps({"version": 3, "owner": "bob", "approved": True}),
                "log.txt": "\n".join(f"event_{i}" for i in range(5000)),
            },
        },
    }

    start = time.perf_counter()

    stored_count = 0
    for user_id, info in users.items():
        passphrase = info["passphrase"]
        for filename, data in info["files"].items():
            storage.store_file(user_id, filename, data, passphrase)
            stored_count += 1

    retrieved_ok = 0
    for user_id, info in users.items():
        passphrase = info["passphrase"]
        file_list = storage.list_files(user_id)
        for filename in file_list:
            content = storage.retrieve_file(user_id, filename, passphrase)
            if content == info["files"][filename]:
                retrieved_ok += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage demonstration summary")
    print(f"Users: {len(users)}")
    print(f"Files stored: {stored_count}")
    print(f"Files retrieved and verified: {retrieved_ok}")
    for user_id in sorted(users):
        listed = storage.list_files(user_id)
        print(f"{user_id}: {len(listed)} files -> {listed}")
    print(f"Time taken: {elapsed:.4f} seconds")


if __name__ == "__main__":
    main()