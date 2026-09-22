#!/usr/bin/env python3
from pathlib import Path
import json
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def load_json(path: Path):
    return json.loads(read(path))

def save_json(path: Path, value) -> None:
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

# ---------------------------------------------------------------------------
# 1) Abyss retry result screen: V0.1.60 rejected a real 815x920-ish capture
#    because aspect 0.886 exceeded the previous hard max 0.86.
#    Keep the three-green-button multi-signal safety rule, but allow the
#    actual portrait capture range up to 0.92.
# ---------------------------------------------------------------------------
retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
retry = read(retry_path)
old_aspect = "aspect < 0.74 || aspect > 0.86"
count = retry.count(old_aspect)
if count < 2:
    raise SystemExit(f"expected at least 2 V0.1.60 aspect guards, found {count}")
retry = retry.replace(old_aspect, "aspect < 0.74 || aspect > 0.92")
marker_anchor = "    private bool TryDetectAbyssResultButtonRow(Bitmap frame, out Rectangle retryRoi)\n"
if marker_anchor not in retry:
    raise SystemExit("TryDetectAbyssResultButtonRow anchor missing")
retry = retry.replace(
    marker_anchor,
    "    // V0161_ABYSS_RESULT_ASPECT_092: real client captures can be ~815x920 (aspect ~0.886).\n"
    + marker_anchor,
    1,
)
write(retry_path, retry)

# ---------------------------------------------------------------------------
# 2) Recovery-potion popup: broaden the proven ESC+닫기 template search area
#    and add the large title OCR as an independent ESC monitor.
#    Either signal can trigger the existing V0.1.60 verified ESC close path.
# ---------------------------------------------------------------------------
def patch_targets(path: Path, close_id: str, title_id: str):
    targets = load_json(path)
    close = next((t for t in targets if t.get("Id") == close_id), None)
    if close is None:
        raise SystemExit(f"missing close target {close_id}: {path}")

    close["Roi"] = {"X": 0, "Y": 500, "Width": 800, "Height": 500}
    close["Threshold"] = 0.70
    close["TemplateScaleMin"] = 0.50
    close["TemplateScaleMax"] = 1.60
    close["TemplateScaleStep"] = 0.05

    targets = [t for t in targets if t.get("Id") != title_id]
    targets.append({
        "Id": title_id,
        "Kind": "ocr",
        "Roi": {"X": 70, "Y": 120, "Width": 660, "Height": 430},
        "Text": "회복 물약이 부족합니다",
        "MaxEditDistance": 3,
        "OcrRetryAt2x": True,
    })
    save_json(path, targets)

patch_targets(app / "abyss" / "config" / "targets.json",
              "abyss_popup_close", "abyss_potion_popup_title")
patch_targets(app / "dungeon" / "config" / "targets.json",
              "potion_popup_close", "potion_popup_title")

def patch_scenario(path: Path, close_id: str, title_id: str):
    scenario = load_json(path)
    monitors = [m for m in scenario.get("Monitors", [])
                if m.get("Target") not in (close_id, title_id)]
    monitors.insert(0, {
        "Target": close_id,
        "Action": "escape",
        "CooldownMs": 3000,
        "ScanIntervalMs": 700,
    })
    monitors.insert(0, {
        "Target": title_id,
        "Action": "escape",
        "CooldownMs": 3000,
        "ScanIntervalMs": 500,
    })
    scenario["Monitors"] = monitors
    save_json(path, scenario)

patch_scenario(app / "abyss" / "config" / "scenario.json",
               "abyss_popup_close", "abyss_potion_popup_title")
patch_scenario(app / "dungeon" / "config" / "scenario.json",
               "potion_popup_close", "potion_popup_title")

# ---------------------------------------------------------------------------
# 3) Version metadata.
# ---------------------------------------------------------------------------
project_path = app / "FishingAutomation.csproj"
project = read(project_path)
for old, new in (
    ("<Version>0.1.60</Version>", "<Version>0.1.61</Version>"),
    ("<AssemblyVersion>0.1.60.0</AssemblyVersion>", "<AssemblyVersion>0.1.61.0</AssemblyVersion>"),
    ("<FileVersion>0.1.60.0</FileVersion>", "<FileVersion>0.1.61.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update_path = app / "UpdateManager.cs"
update = read(update_path)
if 'CurrentVersion = "V0.1.60"' not in update:
    raise SystemExit("UpdateManager V0.1.60 marker missing")
update = update.replace('CurrentVersion = "V0.1.60"', 'CurrentVersion = "V0.1.61"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 4) Safety/static invariants.
# ---------------------------------------------------------------------------
retry = read(retry_path)
if "V0161_ABYSS_RESULT_ASPECT_092" not in retry:
    raise SystemExit("V0.1.61 result aspect marker missing")
if retry.count("aspect < 0.74 || aspect > 0.92") < 2:
    raise SystemExit("V0.1.61 aspect guards not fully updated")
for marker in (
    "exitGreen < 0.18 || retryGreen < 0.18 || otherGreen < 0.18",
    "retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds)",
    'AbyssRequireState(AbyssFlowState.ResultConfirmed, "다시 하기 클릭")',
):
    if marker not in retry:
        raise SystemExit(f"result safety invariant missing: {marker}")

for target_path, close_id, title_id in (
    (app / "abyss" / "config" / "targets.json", "abyss_popup_close", "abyss_potion_popup_title"),
    (app / "dungeon" / "config" / "targets.json", "potion_popup_close", "potion_popup_title"),
):
    targets = load_json(target_path)
    close = next(t for t in targets if t.get("Id") == close_id)
    title = next(t for t in targets if t.get("Id") == title_id)
    if close["Roi"] != {"X": 0, "Y": 500, "Width": 800, "Height": 500}:
        raise SystemExit(f"popup close ROI not broadened: {close_id}")
    if title.get("Kind") != "ocr" or title.get("Text") != "회복 물약이 부족합니다":
        raise SystemExit(f"potion title OCR missing: {title_id}")

for scenario_path, close_id, title_id in (
    (app / "abyss" / "config" / "scenario.json", "abyss_popup_close", "abyss_potion_popup_title"),
    (app / "dungeon" / "config" / "scenario.json", "potion_popup_close", "potion_popup_title"),
):
    scenario = load_json(scenario_path)
    cm = [m for m in scenario.get("Monitors", []) if m.get("Target") == close_id]
    tm = [m for m in scenario.get("Monitors", []) if m.get("Target") == title_id]
    if len(cm) != 1 or cm[0].get("Action") != "escape":
        raise SystemExit(f"ESC close monitor invalid: {close_id}")
    if len(tm) != 1 or tm[0].get("Action") != "escape":
        raise SystemExit(f"ESC title monitor invalid: {title_id}")

engine = read(app / "dungeon" / "ScenarioEngine.cs")
for marker in ("POTION_POPUP_ESC_V1", 'case "escape":', "_input.TapScanCode(0x01);", "ESC 후 닫힘 2프레임 확인"):
    if marker not in engine:
        raise SystemExit(f"V0.1.60 ESC safety path missing: {marker}")

if "<Version>0.1.61</Version>" not in read(project_path):
    raise SystemExit("project version not V0.1.61")
if 'CurrentVersion = "V0.1.61"' not in read(update_path):
    raise SystemExit("updater version not V0.1.61")

print("V0.1.61 applied: Abyss retry aspect fix + potion popup OCR/template ESC detection")
