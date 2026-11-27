#!/usr/bin/env python3
"""Create a Chrome CRX3 package from a built extension directory."""
from pathlib import Path
import hashlib, struct, sys, zipfile
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

EXTENSION_ID = "cdkcnbepbdllejmapkbffamoekdbhplj"

def varint(n):
    out = bytearray()
    while n > 0x7f:
        out.append((n & 0x7f) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)

def field_bytes(number, value):
    return varint((number << 3) | 2) + varint(len(value)) + value

def main():
    if len(sys.argv) != 4:
        raise SystemExit("Usage: sign_crx3.py <extension-dir> <private-key.pem> <output.crx>")
    source, key_path, output = map(Path, sys.argv[1:])
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    pub = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo
    )
    crx_id = hashlib.sha256(pub).digest()[:16]
    actual_id = ''.join(format(b, '02x') for b in crx_id)
    expected_id = ''.join(format(ord(c) - ord('a'), 'x') for c in EXTENSION_ID)
    if actual_id != expected_id:
        raise SystemExit(f"Signing key mismatch: key produces extension ID {actual_id}, expected {EXTENSION_ID}. Refusing to publish an incompatible update.")

    zip_path = output.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(source.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(source).as_posix())
    payload = zip_path.read_bytes()
    signed_header_data = field_bytes(1, crx_id)
    signed_data = b"CRX3 SignedData" + bytes([0]) + struct.pack("<I", len(signed_header_data)) + signed_header_data + payload
    signature = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
    rsa_proof = field_bytes(1, pub) + field_bytes(2, signature)
    header = field_bytes(2, rsa_proof) + field_bytes(10000, signed_header_data)
    output.write_bytes(b"Cr24" + struct.pack("<I", 3) + struct.pack("<I", len(header)) + header + payload)
    print(f"Created {output} ({output.stat().st_size} bytes), extension ID {EXTENSION_ID}")

if __name__ == "__main__":
    main()
