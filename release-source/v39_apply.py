#!/usr/bin/env python3
from pathlib import Path
import json
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


def replace_once(path: Path, pattern: str, replacement: str, flags=0):
    text, enc = read_text(path)
    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"required marker missing: {path}")
    write_text(path, new, enc)


# v39: keep all v38 behavior and only harden Abyss 10-minute forced-exit recognition.
replace_once(
    app / "UpdateManager.cs",
    r'public const string CurrentVersion = "v38";',
    'public const string CurrentVersion = "v39";',
)

# Strengthen only the two forced-exit targets. The normal clear/treasure path is unchanged.
targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(targets_path.read_text(encoding="utf-8-sig"))
seen = set()
for t in targets:
    tid = t.get("Id", "")
    if tid == "abyss_leave_dungeon":
        t["Kind"] = "hybrid"
        t["Text"] = "던전 퇴장"
        t["MaxEditDistance"] = 1
        t["OcrRetryAt2x"] = True
        t["Threshold"] = 0.68
        t["TemplateScaleMin"] = 0.60
        t["TemplateScaleMax"] = 1.50
        t["TemplateScaleStep"] = 0.06
        seen.add(tid)
    elif tid == "abyss_exit":
        t["Kind"] = "hybrid"
        t["Text"] = "나가기"
        t["MaxEditDistance"] = 1
        t["OcrRetryAt2x"] = True
        t["Threshold"] = 0.72
        t["TemplateScaleMin"] = 0.70
        t["TemplateScaleMax"] = 1.40
        t["TemplateScaleStep"] = 0.06
        seen.add(tid)

if seen != {"abyss_leave_dungeon", "abyss_exit"}:
    raise RuntimeError(f"Abyss forced-exit targets missing: {seen}")

targets_path.write_text(json.dumps(targets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# The 10-minute main wait was already correct (600s). Give the forced-exit control
# a little more time to appear after the dungeon timeout; do not change the 10-minute rule.
scenario_path = app / "abyss" / "config" / "scenario.json"
scenario = json.loads(scenario_path.read_text(encoding="utf-8-sig"))
patched = False
for step in scenario.get("Steps", []):
    if step.get("TimeoutClickTarget") == "abyss_leave_dungeon":
        if int(step.get("TimeoutSeconds", 0)) != 600:
            raise RuntimeError("Abyss clear wait is no longer 600 seconds; refusing unexpected patch")
        step["TimeoutClickTargetWaitSeconds"] = 90
        patched = True
        break
if not patched:
    raise RuntimeError("Abyss forced-exit scenario step not found")
scenario_path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Distinct main window title.
p = app / "MainForm.cs"
text, enc = read_text(p)
text = re.sub(r'Text\s*=\s*"MABI AUTO[^\"]*";', 'Text = "MABI AUTO · v39";', text, count=1)
write_text(p, text, enc)

# Cosmetic dashboard labels.
p = app / "MainForm.Dashboard.cs"
if p.exists():
    text, enc = read_text(p)
    text = re.sub(r'Dashboard v\d+', 'Dashboard v39', text)
    text = re.sub(r'v\d+\s*\|\s*Mabi Auto', 'v39  |  Mabi Auto', text)
    write_text(p, text, enc)

# Windows file/product version.
p = app / "FishingAutomation.csproj"
text, enc = read_text(p)
for tag_name, value in {
    "Version": "39.0.0",
    "AssemblyVersion": "39.0.0.0",
    "FileVersion": "39.0.0.0",
}.items():
    pattern = rf'<{tag_name}>[^<]+</{tag_name}>'
    replacement = f'<{tag_name}>{value}</{tag_name}>'
    if re.search(pattern, text):
        text = re.sub(pattern, replacement, text, count=1)
    else:
        text = text.replace("<PropertyGroup>", "<PropertyGroup>\n    " + replacement, 1)
write_text(p, text, enc)

(root / "CHANGES_v39_ABYSS_FORCED_EXIT.txt").write_text(
    "MABI AUTO v39 - Abyss 10-minute forced-exit recognition fix\n\n"
    "- Keeps the correct 600-second (10-minute) clear-screen wait\n"
    "- Forced-exit target abyss_leave_dungeon now uses multiscale template matching plus Korean OCR fallback for '던전 퇴장'\n"
    "- Follow-up abyss_exit now uses multiscale template matching plus OCR fallback for '나가기'\n"
    "- Forced-exit button wait increased from 60s to 90s\n"
    "- Normal Abyss clear, treasure-chest and exit flow is otherwise unchanged\n"
    "- All v38 OpenCV image matching and main-release updater isolation remain intact\n",
    encoding="utf-8",
)

print("v39 applied: hardened Abyss forced-exit recognition without changing normal clear flow")
