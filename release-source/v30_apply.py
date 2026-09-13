#!/usr/bin/env python3
import base64
import hashlib
import io
import pathlib
import sys
import zipfile

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
parts_dir = pathlib.Path(__file__).with_name('v30_parts')
expected = {
    1: 'c720eb48aace5f0c4e79f297ab42c0bbd8b33d78716f665596d67710307be097',
    2: 'bb4dee4f8deb6394a1f419fd0f9287d22076bc8c0a058d0bb4f6cba026383c24',
    3: 'fa45bcd5382508e9013ea36d5cd6aa9792d263a14133da8cc42709cf01e32caa',
    4: '47aa264517cfed9e408fe5fc01a63ce557bbba7ebe59afdfd318e75161e6296b',
    5: '6991a3120ea22becbe5124287597e87c4579fed70ef1118853db4aa7f628e471',
}

chunks = []
for index in range(1, 6):
    part = parts_dir / f'part{index:02d}.txt'
    if not part.is_file():
        raise SystemExit(f'Missing overlay data: {part}')
    raw = part.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected[index]:
        raise SystemExit(f'Overlay part {index:02d} SHA256 mismatch: {digest} != {expected[index]}')
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
