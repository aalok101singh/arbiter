from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pathlib import Path

key_dir = Path(__file__).parent.parent / "keys"
key_dir.mkdir(exist_ok=True)

if (key_dir / "ledger.key").exists():
    print("keys already exist — refusing to overwrite")
    raise SystemExit(1)

private = Ed25519PrivateKey.generate()
(key_dir / "ledger.key").write_bytes(private.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
))
(key_dir / "ledger.pub").write_bytes(private.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
))

print("keys generated in", key_dir)