#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
for rel in ['FishingAutomation/UpdateManager.cs','FishingAutomation/FishingAutomation.csproj','FishingAutomation/MainForm.ReferenceUI.cs']:
    p=root/rel
    print(f'===== {rel} =====')
    lines=p.read_text(encoding='utf-8-sig').splitlines()
    if rel.endswith('UpdateManager.cs'):
        for i,l in enumerate(lines):
            if 'CurrentVersion' in l or 'release' in l.lower() or 'Version' in l or 'tag_name' in l:
                a=max(0,i-8); b=min(len(lines),i+18)
                for j in range(a,b): print(f'{j+1:04d}: {lines[j]}')
                print('---')
    elif rel.endswith('.csproj'):
        for i,l in enumerate(lines[:80]): print(f'{i+1:04d}: {l}')
    else:
        for i,l in enumerate(lines):
            if 'Mabi_Auto' in l or '자동 정지' in l or 'autoStopCheckBounds' in l or 'autoStopTimeBounds' in l or 'Card(g, new(1048' in l:
                a=max(0,i-10); b=min(len(lines),i+18)
                for j in range(a,b): print(f'{j+1:04d}: {lines[j]}')
                print('---')
raise SystemExit(73)
