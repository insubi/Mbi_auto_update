#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
for p in sorted((root/'FishingAutomation').glob('MainForm*.cs')):
    lines=p.read_text(encoding='utf-8-sig').splitlines()
    hits=[]
    for i,l in enumerate(lines):
        if 'CurrentVersion' in l or '최신' in l or 'v72' in l or 'V72' in l:
            hits.append(i)
    if hits:
        print(f'===== {p.relative_to(root)} =====')
        shown=set()
        for i in hits:
            for j in range(max(0,i-5), min(len(lines),i+9)):
                if j not in shown:
                    print(f'{j+1:04d}: {lines[j]}'); shown.add(j)
            print('---')
raise SystemExit(73)
