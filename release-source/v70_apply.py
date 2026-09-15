#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

print("V70_AUTOSTOP_INSPECT_START")
for rel in ["MainForm.ReferenceUI.cs", "MainForm.cs", "MainForm.Dashboard.cs"]:
    p = app / rel
    print(f"===== {rel} =====")
    if not p.is_file():
        print("MISSING")
        continue
    lines = p.read_text(encoding="utf-8-sig").splitlines()
    keys = ("autoStop", "AutoStop", "자동 정지", "DateTimePicker", "CheckBox", "ReferenceDashboard", "TextAt(", "Font")
    hits = [i for i,l in enumerate(lines) if any(k in l for k in keys)]
    shown = set()
    for i in hits:
        a=max(0,i-8); b=min(len(lines),i+14)
        for j in range(a,b):
            if j not in shown:
                print(f"{j+1:04d}: {lines[j]}")
                shown.add(j)
        print("---")
print("V70_AUTOSTOP_INSPECT_END")
sys.exit(70)
