#!/usr/bin/env python3
from pathlib import Path
import base64, gzip, hashlib

# V0.1.2 verified split payload loader.
base = Path(__file__).resolve().parent
parts = []
for i in range(10):
    p = base / f"v75_impl_{i:02d}.b64part"
    if not p.is_file():
        raise RuntimeError(f"V0.1.2 payload part missing: {p.name}")
    parts.append(p.read_text(encoding="ascii").strip())

encoded = "".join(parts)
compressed = base64.b64decode(encoded, validate=True)
compressed_sha = hashlib.sha256(compressed).hexdigest()
if compressed_sha != "f8523c8359731bcdbce63ab739714a888378b873df3ab7742ee093acf55a9157":
    raise RuntimeError(f"V0.1.2 compressed payload SHA mismatch: {compressed_sha}")

source = gzip.decompress(compressed)
source_sha = hashlib.sha256(source).hexdigest()
if source_sha != "ea07d47cc81756d258152fe889419e3719702dd64e575638870e5dc5774cdc36":
    raise RuntimeError(f"V0.1.2 implementation SHA mismatch: {source_sha}")

exec(compile(source.decode("utf-8"), __file__, "exec"))
