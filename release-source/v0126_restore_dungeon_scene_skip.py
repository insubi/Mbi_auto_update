#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0126_restore_dungeon_scene_skip.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
scenario_path = app / "dungeon" / "config" / "scenario.json"
targets_path = app / "dungeon" / "config" / "targets.json"
template_path = app / "dungeon" / "templates" / "scene_skip_phone.jpg"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

if not template_path.exists():
    raise RuntimeError("scene_skip_phone.jpg template missing")

scenario = json.loads(read(scenario_path))
monitors = list(scenario.get("Monitors") or [])
if any(str(m.get("Target", "")).lower() == "scene_skip" for m in monitors):
    raise RuntimeError("scene_skip monitor already exists")
monitors.append({
    "Target": "scene_skip",
    "Action": "click",
    "CooldownMs": 2500,
    "ScanIntervalMs": 1200,
})
scenario["Monitors"] = monitors
write(scenario_path, json.dumps(scenario, ensure_ascii=False, indent=2) + "\n")

targets = json.loads(read(targets_path))
if any(str(t.get("Id", "")).lower() == "scene_skip" for t in targets):
    raise RuntimeError("scene_skip target already exists")
targets.append({
    "Id": "scene_skip",
    "Kind": "hybrid",
    "Roi": {"X": 0, "Y": 0, "Width": 800, "Height": 1000},
    "Text": "장면 넘기기",
    "MaxEditDistance": 1,
    "OcrRetryAt2x": True,
    "TemplatePath": "templates/scene_skip_phone.jpg",
    "Threshold": 0.62,
    "TemplateScaleMin": 0.5,
    "TemplateScaleMax": 1.4,
    "TemplateScaleStep": 0.08,
})
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Runtime version bump only.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.25", "V0.1.26")
                   .replace("0.1.25.0", "0.1.26.0")
                   .replace("0.1.25", "0.1.26"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.26_RESTORE_DUNGEON_SCENE_SKIP.txt").write_text(
    "MABI AUTO V0.1.26 - RESTORE DUNGEON SCENE SKIP MONITOR\n\n"
    "Base: V0.1.25.\n"
    "Restores the dungeon scene_skip monitor removed in V0.1.25.\n"
    "Monitor settings restored: click action, 2500ms cooldown, 1200ms scan interval.\n"
    "Target restored as hybrid OCR/template using scene_skip_phone.jpg with the previous thresholds/scales.\n"
    "V0.1.24 selected/challenge disambiguation, V0.1.23 state-aware ESC recovery, Abyss recovery, and fishing behavior are preserved.\n",
    encoding="utf-8"
)

print("V0.1.26 applied: dungeon scene_skip monitor and target restored")
