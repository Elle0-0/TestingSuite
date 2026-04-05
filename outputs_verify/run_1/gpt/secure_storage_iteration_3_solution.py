import os
import json
import time
import base64
import hashlib
import tempfile
from pathlib import Path
from typing import List

try:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as e:
    raise SystemExit("This program requires the 'cryptography' package installed.") from e


class SecureStorage:
    def __init__(self, root_dir: str = "secure_storage") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        file_id = self._file_id(filename)
        blob_path = user_dir / f"{file_id}.blob"
        meta_path = user_dir / f"{file_id}.meta.json"

        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt)
        nonce = os.urandom(12)

        plaintext = data.encode("utf-8")
        aad = self._aad(user_id, filename)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)

        metadata = {
            "filename": filename,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "size": len(plaintext),
            "updated_at": time.time(),
            "version": 1,
        }

        self._atomic_write_bytes(blob_path, ciphertext)
        self._atomic_write_text(meta_path, json.dumps(metadata, separators=(",", ":")))

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        user_dir = self._user_dir(user_id)
        file_id = self._file_id(filename)
        blob_path = user_dir / f"{file_id}.blob"
        meta_path = user_dir / f"{file_id}.meta.json"

        if not blob_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"File not found for user '{user_id}': {filename}")

        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        salt = base64.b64decode(metadata["salt"])
        nonce = base64.b64decode(metadata["nonce"])
        ciphertext = blob_path.read_bytes()

        key = self._derive_key(passphrase, salt)
        aad = self._aad(user_id, filename)

        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ValueError("Invalid passphrase or file integrity check failed") from e

        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []

        result = []
        for meta_path in user_dir.glob("*.meta.json"):
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                name = metadata.get("filename")
                if isinstance(name, str):
                    result.append(name)
            except Exception:
                continue
        result.sort()
        return result

    def _user_dir(self, user_id: str) -> Path:
        user_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        return self.root / user_hash[:2] / user_hash

    def _file_id(self, filename: str) -> str:
        return hashlib.sha256(filename.encode("utf-8")).hexdigest()

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
        return kdf.derive(passphrase.encode("utf-8"))

    def _aad(self, user_id: str, filename: str) -> bytes:
        return f"{user_id}\0{filename}".encode("utf-8")

    def _atomic_write_bytes(self, path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        os.replace(tmp_name, path)

    def _atomic_write_text(self, path: Path, data: str) -> None:
        self._atomic_write_bytes(path, data.encode("utf-8"))


def main() -> None:
    storage = SecureStorage()

    demo_data = {
        "alice": {
            "passphrase": "alice-strong-pass",
            "files": {
                "notes.txt": "Alice private notes.\nQuarterly planning items.\n",
                "report.md": "# Report\nRevenue looks strong.\nAction items pending.\n",
                "ideas.json": json.dumps({"ideas": ["scaling", "automation", "security"]}),
            },
        },
        "bob": {
            "passphrase": "bob-very-secret",
            "files": {
                "todo.txt": "1. Review contracts\n2. Approve budget\n3. Schedule meeting\n",
                "design.txt": "System design:\n- sharded layout\n- per-file encryption\n- integrity checks\n",
            },
        },
        "carol": {
            "passphrase": "carol-enterprise-key",
            "files": {
                "large_document.txt": ("Confidential section.\n" * 5000),
                "summary.txt": "Multi-file secure storage demonstration.\n",
            },
        },
    }

    start = time.perf_counter()
    stored_count = 0

    for user_id, info in demo_data.items():
        passphrase = info["passphrase"]
        for filename, content in info["files"].items():
            storage.store_file(user_id, filename, content, passphrase)
            stored_count += 1

    retrieved_ok = 0
    for user_id, info in demo_data.items():
        passphrase = info["passphrase"]
        files = storage.list_files(user_id)
        print(f"user={user_id} files={files}")
        for filename in files:
            content = storage.retrieve_file(user_id, filename, passphrase)
            expected = info["files"][filename]
            if content == expected:
                retrieved_ok += 1

    elapsed = time.perf_counter() - start
    print(f"stored_files={stored_count}")
    print(f"retrieved_verified={retrieved_ok}")
    print(f"time_taken_seconds={elapsed:.6f}")


if __name__ == "__main__":
    main()