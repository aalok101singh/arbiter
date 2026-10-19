import json
import hashlib
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical_bytes(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def compute_hash(body):
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def verify(ledger_path: Path, pubkey_path: Path) -> int:
    pub = Ed25519PublicKey.from_public_bytes(pubkey_path.read_bytes())

    prev_hash = "0" * 64
    expected_seq = 0
    count = 0

    with open(ledger_path, "rb") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"FAIL line {lineno}: invalid JSON ({e})")
                return 1

            seq = record.get("seq")
            if seq != expected_seq:
                print(f"FAIL line {lineno}: seq={seq}, expected {expected_seq} (record deleted or reordered)")
                return 1

            stored_hash = record.pop("hash", None)
            stored_sig = record.pop("signature", None)
            if not stored_hash or not stored_sig:
                print(f"FAIL line {lineno}: missing hash or signature")
                return 1

            computed = compute_hash(record)
            if computed != stored_hash:
                print(f"FAIL line {lineno} (seq={seq}): HASH MISMATCH")
                print(f"  stored:   {stored_hash}")
                print(f"  computed: {computed}")
                return 1

            try:
                pub.verify(bytes.fromhex(stored_sig), stored_hash.encode())
            except Exception:
                print(f"FAIL line {lineno} (seq={seq}): SIGNATURE INVALID")
                return 1

            if record["prev_hash"] != prev_hash:
                print(f"FAIL line {lineno} (seq={seq}): CHAIN BROKEN (prev_hash mismatch)")
                return 1

            prev_hash = stored_hash
            expected_seq += 1
            count += 1

    print(f"OK: {count} records, chain intact, all signatures valid")
    return 0


if __name__ == "__main__":
    ledger = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/ledger.jsonl")
    pubkey = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("keys/ledger.pub")
    sys.exit(verify(ledger, pubkey))