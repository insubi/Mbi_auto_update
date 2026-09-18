#!/usr/bin/env python3
from pathlib import Path
import json
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0139_slot_template_fix.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
repo_dir = Path(__file__).resolve().parent
app = root / "FishingAutomation"
targets_path = app / "dungeon" / "config" / "targets.json"
template_dir = app / "dungeon" / "templates"
visual_assets_dir = app / "visual-tests" / "assets"
tester_path = app / "VisualRecognitionTester.cs"
source_templates = repo_dir / "slot-templates"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

template_dir.mkdir(parents=True, exist_ok=True)
visual_assets_dir.mkdir(parents=True, exist_ok=True)
template_map = {
    "route_d1_1": "slot_peaca_d1_1_v0139.jpg",
    "route_d2_1": "slot_peaca_d2_1_v0139.jpg",
    "route_regular_1_1": "slot_regular_1_1_v0139.jpg",
    "route_regular_2_1": "slot_regular_2_1_v0139.jpg",
}

for filename in template_map.values():
    src = source_templates / filename
    dst = template_dir / filename
    if not src.exists():
        raise RuntimeError(f"slot template source missing: {src}")
    shutil.copy2(src, dst)
    shutil.copy2(src, visual_assets_dir / filename)
    if dst.stat().st_size < 500:
        raise RuntimeError(f"slot template unexpectedly small: {dst}")

targets = json.loads(read(targets_path))
by_id = {t.get("Id"): t for t in targets}

roi_map = {
    "route_d1_1": {"X": 255, "Y": 470, "Width": 125, "Height": 125},
    "route_d2_1": {"X": 255, "Y": 760, "Width": 125, "Height": 135},
    "route_regular_1_1": {"X": 255, "Y": 540, "Width": 125, "Height": 125},
    "route_regular_2_1": {"X": 300, "Y": 760, "Width": 125, "Height": 135},
}

for target_id, filename in template_map.items():
    if target_id not in by_id:
        raise RuntimeError(f"slot target missing: {target_id}")
    t = by_id[target_id]
    t["Kind"] = "template"
    t["Roi"] = roi_map[target_id]
    t["TemplatePath"] = f"dungeon/templates/{filename}"
    t["Threshold"] = 0.62
    t["TemplateScaleMin"] = 0.95
    t["TemplateScaleMax"] = 1.05
    t["TemplateScaleStep"] = 0.025
    # Keep the old text only as metadata/debug context. Template kind does not OCR it.
    t["MaxEditDistance"] = 0
    t["OcrRetryAt2x"] = False

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Keep the offline recognition-test UI aligned with the runtime detector.
# The previous D1-1/D2-1 test fixtures were OCR-only synthetic screenshots.
tester = read(tester_path)
old_d11 = '''        await AddTarget(report, progress, "d1-1", "심층 던전 · D1-1",
            "d1_slots.jpg", new Rectangle(160, 400, 470, 250),
            "route_d1_1", ct);
'''
new_d11 = '''        await AddTarget(report, progress, "d1-1", "심층 던전 · D1-1 실제 템플릿",
            "slot_peaca_d1_1_v0139.jpg", new Rectangle(295, 490, 45, 55),
            "route_d1_1", ct);
'''
if old_d11 not in tester:
    raise RuntimeError("visual test D1-1 anchor missing")
tester = tester.replace(old_d11, new_d11, 1)

old_d21 = '''        await AddTarget(report, progress, "d2-1", "심층 던전 · D2-1",
            "d2_slots.jpg", new Rectangle(180, 680, 420, 255),
            "route_d2_1", ct);
'''
new_d21 = '''        await AddTarget(report, progress, "d2-1", "심층 던전 · D2-1 실제 템플릿",
            "slot_peaca_d2_1_v0139.jpg", new Rectangle(295, 800, 45, 50),
            "route_d2_1", ct);

        await AddTarget(report, progress, "regular-1-1", "룬다/피오드 · 1-1 실제 템플릿",
            "slot_regular_1_1_v0139.jpg", new Rectangle(298, 570, 45, 50),
            "route_regular_1_1", ct);

        await AddTarget(report, progress, "regular-2-1", "룬다/피오드 · 2-1 실제 템플릿",
            "slot_regular_2_1_v0139.jpg", new Rectangle(338, 790, 45, 55),
            "route_regular_2_1", ct);
'''
if old_d21 not in tester:
    raise RuntimeError("visual test D2-1 anchor missing")
tester = tester.replace(old_d21, new_d21, 1)
write(tester_path, tester)

# V0.1.38 already expanded arrival wait to five minutes and the slot wait to 30 seconds.
# Keep those safeguards and only change slot detection from OCR to actual visual templates.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.38", "V0.1.39")
                   .replace("0.1.38.0", "0.1.39.0")
                   .replace("0.1.38", "0.1.39"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.39_SLOT_TEMPLATE_FIX.txt").write_text(
    "MABI AUTO V0.1.39 - DUNGEON SLOT VISUAL TEMPLATE FIX\n\n"
    "Replaces OCR-only detection of dungeon 1-1/2-1 tiles with OpenCV grayscale template matching.\n"
    "Templates were cropped from actual Peaca and Runda arrival screens supplied during testing.\n"
    "Peaca uses dedicated D1-1/D2-1 templates. Runda/Fiod share the regular 1-1/2-1 templates as requested.\n"
    "Each target keeps a narrow ROI so adjacent 1-2/1-3/2-2/2-3 tiles cannot be selected as a fallback.\n"
    "V0.1.38 five-minute arrival timeout, 30-second slot wait, purple dungeon-icon click, UI fix and updater survival remain unchanged.\n",
    encoding="utf-8"
)

targets_check = {t.get("Id"): t for t in json.loads(read(targets_path))}
for tid, filename in template_map.items():
    t = targets_check[tid]
    if t.get("Kind") != "template":
        raise RuntimeError(f"{tid} did not switch to template matching")
    if t.get("TemplatePath") != f"dungeon/templates/{filename}":
        raise RuntimeError(f"{tid} template path mismatch")
    if float(t.get("Threshold", 0)) != 0.62:
        raise RuntimeError(f"{tid} threshold mismatch")
    if not (template_dir / filename).exists():
        raise RuntimeError(f"runtime template missing after copy: {filename}")

engine = read(app / "dungeon" / "ScenarioEngine.cs")
if 'WaitForTargetAsync(slotTarget, 30, ct)' not in engine:
    raise RuntimeError("V0.1.38 30-second slot wait was lost")
if 'WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 300, ct)' not in engine:
    raise RuntimeError("V0.1.38 Peaca 5-minute arrival wait was lost")
if 'WaitForTargetAsync(arrivalTarget, 300, ct)' not in engine:
    raise RuntimeError("V0.1.38 Runda/Fiod 5-minute arrival wait was lost")

tester_check = read(tester_path)
for marker in (
    "slot_peaca_d1_1_v0139.jpg",
    "slot_peaca_d2_1_v0139.jpg",
    "slot_regular_1_1_v0139.jpg",
    "slot_regular_2_1_v0139.jpg",
    "route_regular_1_1",
    "route_regular_2_1",
):
    if marker not in tester_check:
        raise RuntimeError("visual recognition test marker missing: " + marker)
for filename in template_map.values():
    if not (visual_assets_dir / filename).exists():
        raise RuntimeError("visual-test template asset missing: " + filename)

print("V0.1.39 patch applied: runtime + recognition-test visual templates for all 1-1/2-1 slots")
