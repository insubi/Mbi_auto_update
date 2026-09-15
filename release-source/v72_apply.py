#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
p=root/'FishingAutomation'/'MainForm.ReferenceUI.cs'
lines=p.read_text(encoding='utf-8-sig').splitlines()
for i,l in enumerate(lines):
    if 'LoadDungeonPreview' in l or '_dungeonPreviews' in l:
        a=max(0,i-8); b=min(len(lines),i+28)
        for j in range(a,b): print(f'{j+1:04d}: {lines[j]}')
        print('---')
raise SystemExit(72)
