#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read_text(path):
    return path.read_text(encoding="utf-8-sig")

def write_text(path, text):
    path.write_text(text, encoding="utf-8-sig")

def replace_once(path, old, new):
    s = read_text(path)
    if old not in s:
        raise RuntimeError(f"pattern not found in {path}: {old}")
    write_text(path, s.replace(old, new, 1))

# Version
replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "v44";',
             'public const string CurrentVersion = "v45";')

p = app / "MainForm.cs"
s = read_text(p).replace('Text = "MABI AUTO · v44";', 'Text = "MABI AUTO · v45";', 1)
write_text(p, s)

# v44 made the category button OCR-only. Restore the known-good v43 visual target
# for step 2. Keep the three actual dungeon selections as exact Korean OCR targets.
p = app / "abyss" / "config" / "targets.json"
targets = json.loads(read_text(p))
found = False
for t in targets:
    if t.get("Id") == "abyss_icon":
        t["Kind"] = "template"
        t["TemplatePath"] = "templates/abyss.png"
        t["Threshold"] = 0.80
        t["TemplateScaleMin"] = 1.0
        t["TemplateScaleMax"] = 1.0
        t["TemplateScaleStep"] = 0.10
        t["Roi"] = {"X": 0, "Y": 0, "Width": 800, "Height": 1000}
        t.pop("Text", None)
        t.pop("MaxEditDistance", None)
        t.pop("OcrRetryAt2x", None)
        found = True
        break
if not found:
    raise RuntimeError("abyss_icon target missing")
write_text(p, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Labels
p = app / "MainForm.Dashboard.cs"
s = read_text(p).replace("Dashboard v44", "Dashboard v45")
s = s.replace('Text = "v44  |  Mabi Auto"', 'Text = "v45  |  Mabi Auto"')
write_text(p, s)

# Assembly version
p = app / "FishingAutomation.csproj"
s = read_text(p)
for key, value in {
    "Version": "45.0.0",
    "AssemblyVersion": "45.0.0.0",
    "FileVersion": "45.0.0.0",
}.items():
    s = re.sub(rf'<{key}>[^<]+</{key}>', f'<{key}>{value}</{key}>', s, count=1)
write_text(p, s)

print("v45: restored Abyss category template; dungeon-name OCR safety retained")
