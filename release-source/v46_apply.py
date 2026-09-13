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

# Version only.
replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "v45";',
             'public const string CurrentVersion = "v46";')

p = app / "MainForm.cs"
s = read_text(p).replace('Text = "MABI AUTO · v45";', 'Text = "MABI AUTO · v46";', 1)
write_text(p, s)

# ONLY change step 3 dungeon selection targets back to their existing image templates.
# Leave abyss menu click, timing, recovery, entry, clear, exit and popup logic untouched.
p = app / "abyss" / "config" / "targets.json"
targets = json.loads(read_text(p))
image_targets = {
    "abyss_dungeon_hallucination_anchorage": "templates/hallucination_anchorage.png",
    "abyss_dungeon_madness_cave": "templates/madness_cave.png",
    "abyss_dungeon_scattered_waterway": "templates/scattered_waterway.png",
}
seen = set()
for t in targets:
    tid = t.get("Id")
    if tid not in image_targets:
        continue
    seen.add(tid)
    t["Kind"] = "template"
    t["TemplatePath"] = image_targets[tid]
    t["Threshold"] = 0.80
    t["TemplateScaleMin"] = 1.0
    t["TemplateScaleMax"] = 1.0
    t["TemplateScaleStep"] = 0.10
    t.pop("Text", None)
    t.pop("MaxEditDistance", None)
    t.pop("OcrRetryAt2x", None)

missing = set(image_targets) - seen
if missing:
    raise RuntimeError("missing Abyss dungeon targets: " + ", ".join(sorted(missing)))
write_text(p, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Version labels only.
p = app / "MainForm.Dashboard.cs"
s = read_text(p).replace("Dashboard v45", "Dashboard v46")
s = s.replace('Text = "v45  |  Mabi Auto"', 'Text = "v46  |  Mabi Auto"')
write_text(p, s)

p = app / "FishingAutomation.csproj"
s = read_text(p)
for key, value in {
    "Version": "46.0.0",
    "AssemblyVersion": "46.0.0.0",
    "FileVersion": "46.0.0.0",
}.items():
    s = re.sub(rf'<{key}>[^<]+</{key}>', f'<{key}>{value}</{key}>', s, count=1)
write_text(p, s)

print("v46: only selected Abyss dungeon targets restored to image templates")
