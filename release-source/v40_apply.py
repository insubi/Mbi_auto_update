#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read_text(path: Path):
    raw = path.read_bytes()
    enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    return raw.decode("utf-8-sig"), enc


def write_text(path: Path, text: str, enc: str):
    path.write_text(text, encoding=enc)


def replace_once(path: Path, old: str, new: str):
    text, enc = read_text(path)
    if old not in text:
        raise RuntimeError(f"required marker missing: {path}")
    write_text(path, text.replace(old, new, 1), enc)


# v40: keep v39 fixes, but fix the root cause found by comparing v29 and v38/v39.
replace_once(
    app / "UpdateManager.cs",
    'public const string CurrentVersion = "v39";',
    'public const string CurrentVersion = "v40";',
)

# In v29 there was no scene_skip monitor. In later versions the monitor is checked
# before the current step target. During Abyss step 5 this can click a false-positive
# scene_skip before abyss_touch_screen gets a chance to match, causing a 10-minute stall.
# For the Abyss clear-screen step ONLY, give abyss_touch_screen first priority. If it is
# not present, scene_skip monitoring continues exactly as before.
engine = app / "Dungeon" / "ScenarioEngine.cs"
text, enc = read_text(engine)
old = '''            using var frame = await CaptureGameWindowAsync(ct);\n\n            if (await CheckMonitorsAsync(frame, ct))\n                continue;\n\n            var found = await _detector.DetectAsync(step.Target, frame, ct);\n            if (found.Found)\n            {'''
new = '''            using var frame = await CaptureGameWindowAsync(ct);\n\n            // Abyss clear screen must win over the global scene-skip monitor.\n            // v29 had no scene-skip monitor and did not miss this screen.\n            // Keep all other steps on the existing monitor-first behavior.\n            DetectionResult found;\n            if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))\n            {\n                found = await _detector.DetectAsync(step.Target, frame, ct);\n                if (!found.Found && await CheckMonitorsAsync(frame, ct))\n                    continue;\n            }\n            else\n            {\n                if (await CheckMonitorsAsync(frame, ct))\n                    continue;\n                found = await _detector.DetectAsync(step.Target, frame, ct);\n            }\n\n            if (found.Found)\n            {'''
if old not in text:
    raise RuntimeError("ScenarioEngine monitor-first marker not found")
text = text.replace(old, new, 1)
write_text(engine, text, enc)

# Window title.
p = app / "MainForm.cs"
text, enc = read_text(p)
text = re.sub(r'Text\s*=\s*"MABI AUTO[^\"]*";', 'Text = "MABI AUTO · v40";', text, count=1)
write_text(p, text, enc)

# Dashboard labels.
p = app / "MainForm.Dashboard.cs"
if p.exists():
    text, enc = read_text(p)
    text = re.sub(r'Dashboard v\d+', 'Dashboard v40', text)
    text = re.sub(r'v\d+\s*\|\s*Mabi Auto', 'v40  |  Mabi Auto', text)
    write_text(p, text, enc)

# Windows version metadata.
p = app / "FishingAutomation.csproj"
text, enc = read_text(p)
for tag_name, value in {
    "Version": "40.0.0",
    "AssemblyVersion": "40.0.0.0",
    "FileVersion": "40.0.0.0",
}.items():
    pattern = rf'<{tag_name}>[^<]+</{tag_name}>'
    replacement = f'<{tag_name}>{value}</{tag_name}>'
    if re.search(pattern, text):
        text = re.sub(pattern, replacement, text, count=1)
    else:
        text = text.replace("<PropertyGroup>", "<PropertyGroup>\n    " + replacement, 1)
write_text(p, text, enc)

(root / "CHANGES_v40_ABYSS_CLEAR_PRIORITY.txt").write_text(
    "MABI AUTO v40 - Abyss clear-screen priority fix\n\n"
    "- Root cause isolated by direct v29 vs v38 comparison\n"
    "- touch_screen.png, threshold 0.84, 600-second wait, and capture code were unchanged\n"
    "- The later scene_skip global monitor was running before abyss_touch_screen detection\n"
    "- Abyss step 5 now checks abyss_touch_screen first\n"
    "- Only when the clear screen is absent does scene_skip monitoring run\n"
    "- scene_skip auto-click remains enabled after dungeon entry\n"
    "- v39 forced-exit recognition hardening remains intact\n"
    "- Fishing/Dungeon behavior otherwise unchanged\n",
    encoding="utf-8",
)

print("v40 applied: Abyss clear screen now has priority over scene_skip monitor")
