#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
print('V66_INSPECT_START')
for rel in [
    'FishingAutomation/MainForm.ReferenceUI.cs',
    'FishingAutomation/MainForm.Dashboard.cs',
    'FishingAutomation/MainForm.cs',
    'FishingAutomation/Dungeon/ScenarioEngine.cs',
    'FishingAutomation/dungeon/config/targets.json',
    'FishingAutomation/dungeon/config/scenario.json',
    'FishingAutomation/abyss/config/targets.json',
    'FishingAutomation/abyss/config/scenario.json',
]:
    p = root / rel
    print(f'===== {rel} =====')
    if p.exists():
        print(p.read_text(encoding='utf-8-sig', errors='replace'))
    else:
        print('MISSING')
print('===== FILES =====')
for p in sorted((root/'FishingAutomation').rglob('*.cs')):
    print(p.relative_to(root).as_posix())
print('===== GREP =====')
keys = ['F10','Stop','CancellationTokenSource','시스템 상태','System Status','Settings','Save','Load','자동 정지']
for p in sorted((root/'FishingAutomation').rglob('*.cs')):
    text = p.read_text(encoding='utf-8-sig', errors='replace')
    hits = [line for line in text.splitlines() if any(k in line for k in keys)]
    if hits:
        print(f'--- {p.relative_to(root).as_posix()} ---')
        for line in hits[:120]:
            print(line)
print('V66_INSPECT_END')
raise SystemExit(66)
