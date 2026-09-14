#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()
s=(root/'FishingAutomation/MainForm.ReferenceUI.cs').read_text(encoding='utf-8-sig', errors='replace')
for needle in ['private ReferenceButton AddButton', '_positions.Add', 'protected override void OnResize', 'private void LayoutControls', 'UpdateAbyssDungeonPickerVisibility']:
    print(f'--- {needle} ---')
    start=0
    while True:
        i=s.find(needle,start)
        if i<0: break
        print(s[max(0,i-1000):min(len(s),i+2200)])
        start=i+1
print('V66_SCALE_INSPECT_END')
raise SystemExit(66)
