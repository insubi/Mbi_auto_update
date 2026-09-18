#!/usr/bin/env python3
from pathlib import Path
import base64
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0136_worldmap_ocr_fix.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
tester_path = app / "VisualRecognitionTester.cs"
targets_path = app / "dungeon" / "config" / "targets.json"
asset_dir = app / "visual-tests" / "assets"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"patch anchor missing: {label}")
    return text.replace(old, new, 1)

asset_dir.mkdir(parents=True, exist_ok=True)
(asset_dir / "peaca_map_actual_v0136.jpg").write_bytes(base64.b64decode("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"))
(asset_dir / "runda_map_actual_v0136.jpg").write_bytes(base64.b64decode("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"))

tester = read(tester_path)
old_peaca = '''        await AddTarget(report, progress, "peaca-map", "월드맵 · 페카 고분 OCR",
            "peaca_label.jpg", new Rectangle(80, 180, 230, 155), "route_peaca_map", ct);
'''
new_peaca = '''        await AddTarget(report, progress, "peaca-map", "월드맵 · 페카 고분 OCR",
            "peaca_map_actual_v0136.jpg", new Rectangle(315, 135, 115, 75), "route_peaca_map", ct);
'''
tester = replace_once(tester, old_peaca, new_peaca, "real Peaca map fixture")

old_runda = '''        var runda = new VisualTestOutcome
        {
            Id = "runda-map",
            Label = "월드맵 · 룬다 던전 OCR",
            Status = "SKIP",
            Method = "OCR",
            Detail = "룬다 던전이 보이는 기존 스크린샷이 아직 없어 테스트를 건너뜁니다."
        };
        report.Outcomes.Add(runda);
        progress?.Report(Format(runda));
'''
new_runda = '''        await AddDirectOcr(report, progress, "runda-map", "월드맵 · 룬다 던전 OCR",
            "runda_map_actual_v0136.jpg", new Rectangle(235, 685, 130, 75),
            new Rectangle(200, 650, 240, 150), "룬다 던전", 2, ct);
'''
tester = replace_once(tester, old_runda, new_runda, "real Runda map fixture")
write(tester_path, tester)

targets = json.loads(read(targets_path))
peaca_targets = [x for x in targets if x.get("Id") == "route_peaca_map"]
if len(peaca_targets) != 1:
    raise RuntimeError(f"route_peaca_map target count unexpected: {len(peaca_targets)}")
peaca_target = peaca_targets[0]
peaca_target["Text"] = "페카 고분"
peaca_target["MaxEditDistance"] = 2
peaca_target["OcrRetryAt2x"] = True
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.35", "V0.1.36")
                   .replace("0.1.35.0", "0.1.36.0")
                   .replace("0.1.35", "0.1.36"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.36_WORLDMAP_OCR.txt").write_text(
    "MABI AUTO V0.1.36 - REAL WORLDMAP OCR FIX\n\n"
    "Uses the user's actual world-map capture crops for Peaca Tomb and Runda Dungeon recognition tests.\n"
    "Peaca route OCR keeps the broad moving-map ROI but allows edit distance 2 and 2x OCR retry.\n"
    "Runda is no longer skipped in the offline recognition test.\n"
    "Existing V0.1.35 visual test upload, V0.1.34 runtime error upload, V0.1.33 retry fast path, dungeon/Abyss/fishing behavior and F10 safety are preserved.\n",
    encoding="utf-8"
)

tester_check = read(tester_path)
targets_check = json.loads(read(targets_path))
if "peaca_map_actual_v0136.jpg" not in tester_check:
    raise RuntimeError("Peaca actual fixture not wired")
if "runda_map_actual_v0136.jpg" not in tester_check or 'Status = "SKIP"' in tester_check:
    raise RuntimeError("Runda actual fixture not wired")
pt = [x for x in targets_check if x.get("Id") == "route_peaca_map"][0]
if int(pt.get("MaxEditDistance", -1)) != 2 or not pt.get("OcrRetryAt2x"):
    raise RuntimeError("route_peaca_map tolerance not applied")
if not (asset_dir / "peaca_map_actual_v0136.jpg").is_file():
    raise RuntimeError("Peaca actual fixture missing")
if not (asset_dir / "runda_map_actual_v0136.jpg").is_file():
    raise RuntimeError("Runda actual fixture missing")

print("V0.1.36 patch applied: real Peaca/Runda world-map OCR fixtures + Peaca tolerance")
