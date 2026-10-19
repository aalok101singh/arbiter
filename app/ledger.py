import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonical_bytes(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def compute_hash(body: dict) -> str:
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def load_private_key(path: Path) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(path.read_bytes())


class Ledger:
    def __init__(self, path: Path, private_key: Ed25519PrivateKey):
        self.path = path
        self.private_key = private_key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _last(self):
        last = None
        with open(self.path, "rb") as f:
            for line in f:
                line = line.strip()
                if line:
                    last = line
        return json.loads(last) if last else None

    def append(self, record: dict) -> dict:
        last = self._last()
        seq = (last["seq"] + 1) if last else 0
        prev_hash = last["hash"] if last else "0" * 64

        body = {
            "seq": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prev_hash": prev_hash,
            **record,
        }
        h = compute_hash(body)
        sig = self.private_key.sign(h.encode()).hex()

        full = {**body, "hash": h, "signature": sig}
        with open(self.path, "ab") as f:
            f.write(json.dumps(full, separators=(",", ":")).encode() + b"\n")
        return full
