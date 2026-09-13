#!/usr/bin/env python3
import base64
import io
import pathlib
import sys
import zipfile

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
parts_dir = pathlib.Path(__file__).with_name('v30_parts')

chunks = []
for index in range(1, 6):
    part = parts_dir / f'part{index:02d}.txt'
    if not part.is_file():
        raise SystemExit(f'Missing overlay data: {part}')
    chunks.append(part.read_text(encoding='utf-8').strip())

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
