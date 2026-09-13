#!/usr/bin/env python3
import base64
import hashlib
import io
import pathlib
import sys
import zipfile

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
parts_dir = pathlib.Path(__file__).with_name('v30_parts')
parts = [
    ('part01.txt', 'c720eb48aace5f0c4e79f297ab42c0bbd8b33d78716f665596d67710307be097'),
    ('part02.txt', 'bb4dee4f8deb6394a1f419fd0f9287d22076bc8c0a058d0bb4f6cba026383c24'),
    ('part03.txt', 'fa45bcd5382508e9013ea36d5cd6aa9792d263a14133da8cc42709cf01e32caa'),
    ('part04.txt', '47aa264517cfed9e408fe5fc01a63ce557bbba7ebe59afdfd318e75161e6296b'),
    ('part05a.txt', '74aa200c2cf75c0c80e6694f2c19107fd16566ab3272294ebb6ec6c52e6f3f57'),
    ('part05b.txt', '1a35859ec2c31c84c10ed1ea5ec75efba287f737291224de5d5bacf33527140d'),
    ('part05c.txt', '63b0a795311350f035a2b7bad67124f4b0b3bde421eefa2e4274e0b41db6de39'),
    ('part05d.txt', '9285f7a06a6de130fab702231fe10208ba43521735ce4e6ee6f3057446c3d061'),
]

chunks = []
for name, expected in parts:
    part = parts_dir / name
    if not part.is_file():
        raise SystemExit(f'Missing overlay data: {part}')
    raw = part.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected:
        raise SystemExit(f'Overlay {name} SHA256 mismatch: {digest} != {expected}')
    chunks.append(raw.decode('ascii').strip())

payload = base64.b64decode(''.join(chunks), validate=True)
with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit(f'Overlay ZIP CRC check failed: {bad}')
    for info in archive.infolist():
        target = (root / info.filename).resolve()
        if root != target and root not in target.parents:
            raise SystemExit(f'Unsafe ZIP entry: {info.filename}')
    archive.extractall(root)

print(f'Applied verified v30 overlay to {root}')
