#!/usr/bin/env python3
"""Apply only reviewed additions/integration edits to the exact v32 release."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent
manifest = json.loads((here / 'manifest.json').read_text(encoding='utf-8'))
entries = manifest['files']
for entry in entries:
    target = (root / entry['path']).resolve()
    source = (here / 'overlay' / entry['path']).resolve()
    if not target.is_relative_to(root) or not source.is_relative_to(here / 'overlay'):
        raise SystemExit('Unsafe overlay path')
    if hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
        raise SystemExit('Overlay checksum mismatch: ' + entry['path'])
    previous = entry['base_sha256']
    if previous is None:
        if target.exists():
            raise SystemExit('Expected new path already exists: ' + entry['path'])
    elif not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != previous:
        raise SystemExit('v32 baseline mismatch: ' + entry['path'])

before = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in root.rglob('*') if p.is_file()}
for entry in entries:
    target = root / entry['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(here / 'overlay' / entry['path'], target)

changed = {entry['path'] for entry in entries}
for relative, digest in before.items():
    if relative not in changed and hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
        raise SystemExit('Unrelated v32 file changed: ' + relative)
print(f'v33 overlay applied; {len(entries)} files added/changed; all other v32 bytes preserved.')
