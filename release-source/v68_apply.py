#!/usr/bin/env python3
from pathlib import Path
import json, sys
root = Path(sys.argv[1]).resolve()
app = root / 'FishingAutomation'
print('V68_INSPECT_START')
for rel in ['abyss/config/targets.json','abyss/config/scenario.json','abyss/config/scenarios.json']:
    p = app / rel
    if p.is_file():
        print('===== ' + rel + ' =====')
        print(p.read_text(encoding='utf-8-sig'))
print('V68_INSPECT_END')
raise SystemExit(68)
