#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0142_entry_exact_click_fix.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
detector_path = app / "dungeon" / "TargetDetector.cs"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
targets_path = app / "dungeon" / "config" / "targets.json"
reference_ui_path = app / "MainForm.ReferenceUI.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

# 1) Restore a bottom-only entry ROI adapted to the current 800x1000 client.
# V0.1.24 searched only the bottom strip. V0.1.41 had widened this upward to Y=825,
# allowing unrelated neighboring controls to share the OCR line.
targets = json.loads(read(targets_path))
by_id = {t.get("Id"): t for t in targets}
for tid in ("enter_bottom", "enter_confirm"):
    if tid not in by_id:
        raise RuntimeError(f"missing target: {tid}")
    t = by_id[tid]
    t["Roi"] = {"X": 0, "Y": 900, "Width": 800, "Height": 100}
    t["Text"] = "입장하기"
    t["MaxEditDistance"] = 0
    t["OcrRetryAt2x"] = True

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# 2) For clickable entry text, use the existing exact compact-word OCR.
# This returns only the matched word(s) bounding box, not the whole OCR line.
detector = read(detector_path)
old = '''            bool exactDungeonSlot =
                id.Equals("route_d1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_d2_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_2_1", StringComparison.OrdinalIgnoreCase);

            if (exactDungeonSlot)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, ct);

            return await _ocr.FindTextAsync(frame, roi, t.Text, t.MaxEditDistance, t.OcrRetryAt2x, ct);
'''
new = '''            bool exactDungeonSlot =
                id.Equals("route_d1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_d2_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_2_1", StringComparison.OrdinalIgnoreCase);

            bool exactClickableEntry =
                id.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("enter_confirm", StringComparison.OrdinalIgnoreCase);

            if (exactDungeonSlot || exactClickableEntry)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, ct);

            return await _ocr.FindTextAsync(frame, roi, t.Text, t.MaxEditDistance, t.OcrRetryAt2x, ct);
'''
detector = replace_once(detector, old, new, "exact entry OCR")
write(detector_path, detector)

# 3) Final click guard: entry click is allowed only if the detector returned
# an exact normalized '입장하기' word candidate. Never click a line-wide/ambiguous result.
engine = read(engine_path)
old_click = '''                    else
                    {
                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(_settings.ClickSettleMs, ct);
                    }
'''
new_click = '''                    else
                    {
                        if (step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase))
                        {
                            string exactEntry = FuzzyText.Normalize(found.ReadText ?? "");
                            if (!exactEntry.Equals(FuzzyText.Normalize("입장하기"), StringComparison.OrdinalIgnoreCase))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기 정확 단어 확인 실패 -> 클릭 안 함 · OCR=\"{found.ReadText}\" @ {found.Bounds}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            Log?.Invoke($"[던전 입장] 입장하기 단어 자체 중앙 클릭 @ {found.Bounds} center={found.Center}");
                        }

                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(_settings.ClickSettleMs, ct);
                    }
'''
engine = replace_once(engine, old_click, new_click, "entry exact click guard")
write(engine_path, engine)

# 4) Recognition navigation label: shorten to "인식" and restore the same
# left-side image icon used by the other navigation buttons.
reference_ui = read(reference_ui_path)
reference_ui = replace_once(
    reference_ui,
    'AddButton("인식 테스트", new(18, 511, 178, 59), owner.ShowVisualRecognitionTest, "", "nav");',
    'AddButton("인식", new(18, 511, 170, 59), owner.ShowVisualRecognitionTest, "image", "nav");',
    "recognition nav label/icon")
write(reference_ui_path, reference_ui)

# 5) Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.41", "V0.1.42")
                   .replace("0.1.41.0", "0.1.42.0")
                   .replace("0.1.41", "0.1.42"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.42_ENTRY_EXACT_CLICK_FIX.txt").write_text(
    "MABI AUTO V0.1.42 - EXACT ENTRY BUTTON CLICK\n\n"
    "Keeps the proven V0.1.24 selected/challenge disambiguation behavior.\n"
    "Restores the dungeon '입장하기' OCR search to a bottom-only region adapted to the current 800x1000 client (Y=900..999).\n"
    "enter_bottom and enter_confirm now use exact compact-word OCR, which returns only the matched '입장하기' word bounding box rather than the entire OCR line.\n"
    "If Windows OCR reads '파티찾기 입장하기' on one line, only the '입장하기' word bounds are eligible for clicking.\n"
    "A final click guard rejects any enter_bottom result whose normalized OCR text is not exactly '입장하기'.\n"
    "The log records the exact entry word bounds and center used for the click.\n"
    "The left navigation label is shortened from '인식 테스트' to '인식' and uses the standard image icon so it no longer clips.\n",
    encoding="utf-8"
)

# Structural verification.
targets_check = {t.get("Id"): t for t in json.loads(read(targets_path))}
for tid in ("enter_bottom", "enter_confirm"):
    t = targets_check[tid]
    if t["Roi"] != {"X": 0, "Y": 900, "Width": 800, "Height": 100}:
        raise RuntimeError(f"{tid} ROI mismatch: {t['Roi']}")
    if t.get("Text") != "입장하기" or int(t.get("MaxEditDistance", -1)) != 0:
        raise RuntimeError(f"{tid} exact OCR config mismatch")

detector_check = read(detector_path)
engine_check = read(engine_path)
reference_ui_check = read(reference_ui_path)
if 'AddButton("인식", new(18, 511, 170, 59), owner.ShowVisualRecognitionTest, "image", "nav");' not in reference_ui_check:
    raise RuntimeError("recognition nav label/icon fix missing")
if 'AddButton("인식 테스트"' in reference_ui_check:
    raise RuntimeError("old clipped recognition-test label remains")

for marker in (
    "bool exactClickableEntry",
    'id.Equals("enter_bottom"',
    'id.Equals("enter_confirm"',
    "FindCompactLabelAsync(frame, roi, t.Text, ct)",
):
    if marker not in detector_check:
        raise RuntimeError("detector marker missing: " + marker)

for marker in (
    "입장하기 정확 단어 확인 실패 -> 클릭 안 함",
    "입장하기 단어 자체 중앙 클릭",
    'FuzzyText.Normalize("입장하기")',
):
    if marker not in engine_check:
        raise RuntimeError("entry click guard marker missing: " + marker)

print("V0.1.42 patch applied: exact entry-word click + recognition nav label/icon fix")
