import os
import json
import time
import base64
import hashlib
import hmac
import tempfile
from pathlib import Path
from typing import List

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as e:
    raise RuntimeError("This solution requires the 'cryptography' package.") from e


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        nonce = os.urandom(12)

        plaintext = data.encode("utf-8")
        aad = self._aad_bytes(user_id, filename)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)

        payload = {
            "v": 1,
            "alg": "AES-256-GCM",
            "kdf": "PBKDF2-HMAC-SHA256",
            "iter": 200000,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ct": base64.b64encode(ciphertext).decode("ascii"),
        }

        target = user_dir / self._safe_name(filename)
        self._atomic_write_json(target, payload)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        path = self._user_dir(user_id) / self._safe_name(filename)
        if not path.exists():
            raise FileNotFoundError(f"File not found: user_id={user_id!r}, filename={filename!r}")

        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        salt = base64.b64decode(payload["salt"])
        nonce = base64.b64decode(payload["nonce"])
        ciphertext = base64.b64decode(payload["ct"])
        key = self._derive_key(passphrase, salt, payload.get("iter", 200000))
        aad = self._aad_bytes(user_id, filename)

        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ValueError("Invalid passphrase or file integrity check failed") from e

        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []

        files = []
        for p in user_dir.iterdir():
            if p.is_file() and p.suffix == ".enc":
                try:
                    stem = p.stem
                    decoded = base64.urlsafe_b64decode(self._pad_b64(stem)).decode("utf-8")
                    files.append(decoded)
                except Exception:
                    continue
        files.sort()
        return files

    def _user_dir(self, user_id: str) -> Path:
        return self.root / self._user_bucket(user_id) / self._safe_user(user_id)

    def _safe_user(self, user_id: str) -> str:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
        return f"user_{digest}"

    def _user_bucket(self, user_id: str) -> str:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return digest[:2]

    def _safe_name(self, filename: str) -> str:
        encoded = base64.urlsafe_b64encode(filename.encode("utf-8")).decode("ascii").rstrip("=")
        return f"{encoded}.enc"

    def _pad_b64(self, s: str) -> str:
        return s + "=" * (-len(s) % 4)

    def _derive_key(self, passphrase: str, salt: bytes, iterations: int = 200000) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)

    def _aad_bytes(self, user_id: str, filename: str) -> bytes:
        return json.dumps(
            {"user_id": user_id, "filename": filename},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def _atomic_write_json(self, target: Path, payload: dict) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(payload, tmp, separators=(",", ":"))
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass


def main() -> None:
    storage = SecureStorage("secure_storage_demo")

    dataset = {
        "alice": {
            "passphrase": "alice-strong-passphrase",
            "files": {
                "notes.txt": "Alice private meeting notes",
                "report.md": "# Q4 Report\nRevenue up 12%\nConfidential",
                "archive/log1.txt": "Event log entry A\nEvent log entry B",
            },
        },
        "bob": {
            "passphrase": "bob-very-secure-passphrase",
            "files": {
                "todo.txt": "1. Review design\n2. Approve rollout",
                "draft.txt": "Initial draft for enterprise deployment",
            },
        },
        "carol": {
            "passphrase": "carol-ultra-passphrase",
            "files": {
                "large.txt": "LARGE-DATA-" * 10000,
                "summary.json": '{"status":"ok","items":1024}',
            },
        },
    }

    start = time.perf_counter()
    stored_count = 0

    for user_id, info in dataset.items():
        for filename, data in info["files"].items():
            storage.store_file(user_id, filename, data, info["passphrase"])
            stored_count += 1

    retrieved_ok = 0
    for user_id, info in dataset.items():
        listed = storage.list_files(user_id)
        for filename in listed:
            content = storage.retrieve_file(user_id, filename, info["passphrase"])
            if content == info["files"][filename]:
                retrieved_ok += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage demo complete")
    print(f"Users: {len(dataset)}")
    print(f"Files stored: {stored_count}")
    print(f"Files retrieved and verified: {retrieved_ok}")
    for user_id in sorted(dataset):
        print(f"{user_id}: {len(storage.list_files(user_id))} files -> {storage.list_files(user_id)}")
    print(f"Time taken: {elapsed:.4f} seconds")


if __name__ == "__main__":
    main()