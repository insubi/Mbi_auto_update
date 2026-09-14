#!/usr/bin/env python3
from pathlib import Path
import hashlib, sys

root = Path(sys.argv[1]).resolve()
print('V66_ENGINE_INSPECT_START')
for rel in [
    'FishingAutomation/dungeon/ScenarioEngine.cs',
    'FishingAutomation/dungeon/TargetDetector.cs',
    'FishingAutomation/dungeon/Models.cs',
    'FishingAutomation/dungeon/TemplateMatcher.cs',
]:
    p = root / rel
    print(f'===== {rel} =====')
    print(p.read_text(encoding='utf-8-sig', errors='replace') if p.exists() else 'MISSING')
for folder in ['FishingAutomation/dungeon/templates','FishingAutomation/abyss/templates']:
    print(f'===== {folder} =====')
    p = root / folder
    if p.exists():
        for f in sorted(x for x in p.iterdir() if x.is_file()):
            print(f'{f.name}\t{f.stat().st_size}\t{hashlib.sha256(f.read_bytes()).hexdigest()}')
print('V66_ENGINE_INSPECT_END')
raise SystemExit(66)
