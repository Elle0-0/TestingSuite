import os
import json
import time
import hmac
import shutil
import hashlib
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple


class SecureStorage:
    def __init__(self, base_dir: str = "secure_storage_data") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir = self.base_dir / "users"
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self.pbkdf2_iterations = 200_000
        self.chunk_size = 1024 * 1024

    def store_file(self, user_id: str, filename: str, data: str, passphrase: str) -> None:
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        file_path = user_dir / self._safe_name(filename)
        salt = os.urandom(16)
        enc_key, mac_key = self._derive_keys(passphrase, salt)

        plaintext = data.encode("utf-8")
        nonce = os.urandom(16)
        ciphertext = self._xor_stream_encrypt(plaintext, enc_key, nonce)
        mac = self._compute_mac(salt, nonce, ciphertext, mac_key)

        payload = {
            "version": 1,
            "filename": filename,
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "ciphertext": ciphertext.hex(),
            "mac": mac.hex(),
        }

        self._atomic_write_json(file_path, payload)

    def retrieve_file(self, user_id: str, filename: str, passphrase: str) -> str:
        file_path = self._user_dir(user_id) / self._safe_name(filename)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found for user '{user_id}': {filename}")

        with file_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        salt = bytes.fromhex(payload["salt"])
        nonce = bytes.fromhex(payload["nonce"])
        ciphertext = bytes.fromhex(payload["ciphertext"])
        stored_mac = bytes.fromhex(payload["mac"])

        enc_key, mac_key = self._derive_keys(passphrase, salt)
        calc_mac = self._compute_mac(salt, nonce, ciphertext, mac_key)

        if not hmac.compare_digest(stored_mac, calc_mac):
            raise ValueError("Integrity check failed or incorrect passphrase")

        plaintext = self._xor_stream_encrypt(ciphertext, enc_key, nonce)
        return plaintext.decode("utf-8")

    def list_files(self, user_id: str) -> List[str]:
        user_dir = self._user_dir(user_id)
        if not user_dir.exists():
            return []

        names = []
        for path in user_dir.iterdir():
            if not path.is_file() or path.suffix != ".json":
                continue
            try:
                with path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                names.append(payload.get("filename", path.stem))
            except Exception:
                names.append(path.stem)
        names.sort()
        return names

    def _user_dir(self, user_id: str) -> Path:
        return self.users_dir / self._safe_name(user_id, allow_ext=False)

    def _safe_name(self, value: str, allow_ext: bool = True) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{digest}.json" if allow_ext else digest

    def _derive_keys(self, passphrase: str, salt: bytes) -> Tuple[bytes, bytes]:
        key_material = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase.encode("utf-8"),
            salt,
            self.pbkdf2_iterations,
            dklen=64,
        )
        return key_material[:32], key_material[32:]

    def _keystream_block(self, key: bytes, nonce: bytes, counter: int) -> bytes:
        return hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()

    def _xor_stream_encrypt(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        out = bytearray(len(data))
        offset = 0
        counter = 0
        total = len(data)
        while offset < total:
            block = self._keystream_block(key, nonce, counter)
            take = min(len(block), total - offset)
            chunk = data[offset:offset + take]
            for i in range(take):
                out[offset + i] = chunk[i] ^ block[i]
            offset += take
            counter += 1
        return bytes(out)

    def _compute_mac(self, salt: bytes, nonce: bytes, ciphertext: bytes, mac_key: bytes) -> bytes:
        mac = hmac.new(mac_key, digestmod=hashlib.sha256)
        mac.update(b"v1")
        mac.update(salt)
        mac.update(nonce)
        mac.update(ciphertext)
        return mac.digest()

    def _atomic_write_json(self, path: Path, payload: Dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(payload, tmp_file, separators=(",", ":"))
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.remove(tmp_name)
            except OSError:
                pass
            raise


def main() -> None:
    demo_dir = "secure_storage_demo"
    if os.path.exists(demo_dir):
        shutil.rmtree(demo_dir)

    storage = SecureStorage(demo_dir)

    users = {
        "alice": {
            "passphrase": "alice-strong-passphrase",
            "files": {
                "notes.txt": "Alice private notes.\n" * 200,
                "budget.csv": "month,amount\njan,1200\nfeb,1100\nmar,1300\n",
                "report.md": "# Quarterly Report\n" + ("Confidential section\n" * 300),
            },
        },
        "bob": {
            "passphrase": "bob-strong-passphrase",
            "files": {
                "todo.txt": "1. Review contracts\n2. Approve invoices\n",
                "design.txt": "System design draft\n" * 500,
            },
        },
        "carol": {
            "passphrase": "carol-strong-passphrase",
            "files": {
                "archive.log": "event=ok\n" * 1000,
                "memo.txt": "Internal memo for Carol.\n" * 150,
                "plans.json": json.dumps({"phase1": "done", "phase2": "active", "phase3": "planned"}),
            },
        },
    }

    start = time.perf_counter()
    stored_count = 0

    for user_id, info in users.items():
        pw = info["passphrase"]
        for filename, content in info["files"].items():
            storage.store_file(user_id, filename, content, pw)
            stored_count += 1

    retrieved_ok = 0
    for user_id, info in users.items():
        pw = info["passphrase"]
        file_list = storage.list_files(user_id)
        for filename in file_list:
            data = storage.retrieve_file(user_id, filename, pw)
            if data == info["files"][filename]:
                retrieved_ok += 1

    elapsed = time.perf_counter() - start

    print("SecureStorage demonstration complete")
    print(f"Users: {len(users)}")
    print(f"Files stored: {stored_count}")
    print(f"Files retrieved and verified: {retrieved_ok}")
    for user_id in sorted(users):
        print(f"{user_id}: {len(storage.list_files(user_id))} files -> {storage.list_files(user_id)}")
    print(f"Time taken: {elapsed:.6f} seconds")


if __name__ == "__main__":
    main()