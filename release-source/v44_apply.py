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


# Version bump only. Gameplay flow outside Abyss menu/dungeon selection remains unchanged.
replace_once(
    app / "UpdateManager.cs",
    'public const string CurrentVersion = "v43";',
    'public const string CurrentVersion = "v44";')

p = app / "MainForm.cs"
s = read_text(p)
s = s.replace('Text = "MABI AUTO · v43";', 'Text = "MABI AUTO · v44";', 1)
write_text(p, s)

# v43 searched a small Abyss icon and three dungeon-card templates across the entire
# 800x1000 frame. Similar cards could be clicked. For navigation targets, use the
# visible Korean label as the click anchor so a differently named card is not clicked.
p = app / "abyss" / "config" / "targets.json"
targets = json.loads(read_text(p))

ocr_targets = {
    "abyss_icon": ("어비스", 0),
    "abyss_dungeon_hallucination_anchorage": ("허상의 정박지", 1),
    "abyss_dungeon_madness_cave": ("광기의 동굴", 1),
    "abyss_dungeon_scattered_waterway": ("흩어진 물길", 1),
}

seen = set()
for t in targets:
    tid = t.get("Id")
    if tid not in ocr_targets:
        continue
    text, distance = ocr_targets[tid]
    seen.add(tid)
    t["Kind"] = "ocr"
    t["Text"] = text
    t["MaxEditDistance"] = distance
    t["OcrRetryAt2x"] = True
    t["Roi"] = {"X": 0, "Y": 0, "Width": 800, "Height": 1000}

missing = set(ocr_targets) - seen
if missing:
    raise RuntimeError("missing Abyss targets: " + ", ".join(sorted(missing)))

write_text(p, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Dashboard/version labels only.
p = app / "MainForm.Dashboard.cs"
s = read_text(p)
s = s.replace("Dashboard v43", "Dashboard v44")
s = s.replace('Text = "v43  |  Mabi Auto"', 'Text = "v44  |  Mabi Auto"')
write_text(p, s)

# Assembly version.
p = app / "FishingAutomation.csproj"
s = read_text(p)
for key, value in {
    "Version": "44.0.0",
    "AssemblyVersion": "44.0.0.0",
    "FileVersion": "44.0.0.0",
}.items():
    s = re.sub(rf'<{key}>[^<]+</{key}>', f'<{key}>{value}</{key}>', s, count=1)
write_text(p, s)

print("v44 Abyss safe text-target selection patch applied")
