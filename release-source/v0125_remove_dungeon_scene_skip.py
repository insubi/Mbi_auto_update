#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0125_remove_dungeon_scene_skip.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
scenario_path = app / "dungeon" / "config" / "scenario.json"
targets_path = app / "dungeon" / "config" / "targets.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

scenario = json.loads(read(scenario_path))
monitors = list(scenario.get("Monitors") or [])
scenario["Monitors"] = [m for m in monitors if str(m.get("Target", "")).lower() != "scene_skip"]
if len(scenario["Monitors"]) == len(monitors):
    raise RuntimeError("scene_skip monitor was not found in dungeon scenario")
write(scenario_path, json.dumps(scenario, ensure_ascii=False, indent=2) + "\n")

targets = json.loads(read(targets_path))
new_targets = [t for t in targets if str(t.get("Id", "")).lower() != "scene_skip"]
if len(new_targets) == len(targets):
    raise RuntimeError("scene_skip target was not found in dungeon targets")
write(targets_path, json.dumps(new_targets, ensure_ascii=False, indent=2) + "\n")

# Runtime version bump only.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.24", "V0.1.25")
                   .replace("0.1.24.0", "0.1.25.0")
                   .replace("0.1.24", "0.1.25"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.25_REMOVE_DUNGEON_SCENE_SKIP.txt").write_text(
    "MABI AUTO V0.1.25 - REMOVE DUNGEON SCENE SKIP MONITOR\n\n"
    "Base: V0.1.24.\n"
    "Removed the dungeon scene_skip monitor so dungeon automation no longer scans for or clicks the scene-skip target.\n"
    "Removed the scene_skip target from dungeon targets.json.\n"
    "V0.1.24 selected/challenge disambiguation, V0.1.23 state-aware ESC recovery, Abyss recovery, and fishing behavior are preserved.\n",
    encoding="utf-8"
)

print("V0.1.25 applied: dungeon scene_skip monitor and target removed")
