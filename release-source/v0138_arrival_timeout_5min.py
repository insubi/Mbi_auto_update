#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0138_arrival_timeout_5min.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
ocr_path = app / "dungeon" / "OcrRecognizer.cs"
detector_path = app / "dungeon" / "TargetDetector.cs"
targets_path = app / "dungeon" / "config" / "targets.json"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

engine = read(engine_path)

engine = replace_once(
    engine,
    'bool arrived = await WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 30, ct);',
    'bool arrived = await WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 300, ct);',
    "Peaca arrival timeout")
engine = replace_once(
    engine,
    'throw new TimeoutException("이동 후 30초 안에 페카 고분 도착/심층 던전 탭을 확인하지 못했습니다.");',
    'throw new TimeoutException("이동 후 5분 안에 페카 고분 도착/심층 던전 탭을 확인하지 못했습니다.");',
    "Peaca timeout message")
engine = replace_once(
    engine,
    'var arrived = await WaitForTargetAsync(arrivalTarget, 30, ct);',
    'var arrived = await WaitForTargetAsync(arrivalTarget, 300, ct);',
    "Runda/Fiod arrival timeout")
engine = replace_once(
    engine,
    'throw new TimeoutException($"이동 후 30초 안에 {dungeonName} 도착 화면을 확인하지 못했습니다.");',
    'throw new TimeoutException($"이동 후 5분 안에 {dungeonName} 도착 화면을 확인하지 못했습니다.");',
    "Runda/Fiod timeout message")
write(engine_path, engine)

# All dungeon 1-1 / 2-1 markers are tiny white labels. V0.1.37 only retried OCR at 2x,
# which missed a real Peaca D2-1 screen even though the ROI contained the label.
# Add a compact-label OCR path that retries 1x -> 2x -> 3x -> 4x, and use it only
# for the six requested slot choices (Peaca/Runda/Fiod 1-1 and 2-1).
ocr = read(ocr_path)
ocr_anchor = '''    public async Task<DetectionResult> FindTextAsync(Bitmap frame, Rectangle roi, string wanted, int maxEditDistance, bool retry2x, CancellationToken ct)
    {
        var result = await FindAtScaleAsync(frame, roi, wanted, maxEditDistance, 1, ct);
        if (result.Found || !retry2x) return result;
        return await FindAtScaleAsync(frame, roi, wanted, maxEditDistance, 2, ct);
    }
'''
ocr_insert = ocr_anchor + '''
    public async Task<DetectionResult> FindCompactLabelAsync(Bitmap frame, Rectangle roi, string wanted, int maxEditDistance, CancellationToken ct)
    {
        foreach (int scale in new[] { 1, 2, 3, 4 })
        {
            var result = await FindAtScaleAsync(frame, roi, wanted, maxEditDistance, scale, ct);
            if (result.Found) return result;
        }
        return DetectionResult.NotFound;
    }
'''
ocr = replace_once(ocr, ocr_anchor, ocr_insert, "compact label OCR scales")
write(ocr_path, ocr)

detector = read(detector_path)
detector_anchor = '''        if (t.Kind.Equals("ocr", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(t.Text)) return DetectionResult.NotFound;
            return await _ocr.FindTextAsync(frame, roi, t.Text, t.MaxEditDistance, t.OcrRetryAt2x, ct);
        }
'''
detector_new = '''        if (t.Kind.Equals("ocr", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(t.Text)) return DetectionResult.NotFound;

            bool compactDungeonSlot =
                id.Equals("route_d1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_d2_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_2_1", StringComparison.OrdinalIgnoreCase);

            if (compactDungeonSlot)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, t.MaxEditDistance, ct);

            return await _ocr.FindTextAsync(frame, roi, t.Text, t.MaxEditDistance, t.OcrRetryAt2x, ct);
        }
'''
detector = replace_once(detector, detector_anchor, detector_new, "compact dungeon slot detector")
write(detector_path, detector)

# Unify Peaca/Runda/Fiod slot targets. We deliberately search for "1-1"/"2-1"
# rather than requiring the optional D prefix; FuzzyText normalization then matches
# D1-1/D2-1 as well as plain 1-1/2-1.
import json
targets = json.loads(read(targets_path))
slot_updates = {
    "route_d1_1": {
        "Roi": {"X": 160, "Y": 420, "Width": 380, "Height": 270},
        "Text": "1-1",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    },
    "route_d2_1": {
        "Roi": {"X": 160, "Y": 680, "Width": 400, "Height": 280},
        "Text": "2-1",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    },
    "route_regular_1_1": {
        "Roi": {"X": 160, "Y": 420, "Width": 380, "Height": 270},
        "Text": "1-1",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    },
    "route_regular_2_1": {
        "Roi": {"X": 160, "Y": 680, "Width": 400, "Height": 280},
        "Text": "2-1",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    },
}
seen = set()
for target in targets:
    tid = target.get("Id")
    if tid in slot_updates:
        target.update(slot_updates[tid])
        seen.add(tid)

missing = set(slot_updates) - seen
if missing:
    raise RuntimeError("slot OCR targets missing: " + ", ".join(sorted(missing)))

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Give the selected 1-1/2-1 label up to 30 seconds to become readable after arrival.
engine = read(engine_path)
engine = replace_once(
    engine,
    'var slot = await WaitForTargetAsync(slotTarget, 10, ct);',
    'var slot = await WaitForTargetAsync(slotTarget, 30, ct);',
    "all dungeon slot wait")
engine = replace_once(
    engine,
    'throw new TimeoutException($"{destination}의 {(d11 ? "1-1" : "2-1")} 표기를 10초 안에 찾지 못했습니다. 다른 구역을 대신 누르지 않습니다.");',
    'throw new TimeoutException($"{destination}의 {(d11 ? "1-1" : "2-1")} 표기를 30초 안에 찾지 못했습니다. 다른 구역을 대신 누르지 않습니다.");',
    "all dungeon slot wait message")
write(engine_path, engine)

# Version bump from the current release line.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.37", "V0.1.38")
                   .replace("0.1.37.0", "0.1.38.0")
                   .replace("0.1.37", "0.1.38"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.38_ARRIVAL_TIMEOUT_5MIN.txt").write_text(
    "MABI AUTO V0.1.38 - DUNGEON ARRIVAL + 1-1/2-1 OCR FIX\n\n"
    "Changes dungeon travel arrival verification from 30 seconds to 5 minutes (300 seconds).\n"
    "Applies to Peaca Tomb, Runda Dungeon and Fiod Dungeon auto-route arrival waits.\n"
    "Peaca/Runda/Fiod 1-1 and 2-1 markers now share wider ROIs and compact-label OCR retries at 1x/2x/3x/4x.\n"
    "Slot matching searches 1-1/2-1 so it accepts Peaca D1-1/D2-1 as well as regular 1-1/2-1 labels.\n"
    "Only 1-1 and 2-1 are used; 1-2/1-3/2-2/2-3 remain ignored.\n"
    "All V0.1.37 dungeon-icon clicking, recognition UI, updater-survival and safety behavior are preserved.\n",
    encoding="utf-8"
)

check = read(engine_path)
for marker in (
    'WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 300, ct)',
    'WaitForTargetAsync(arrivalTarget, 300, ct)',
    '이동 후 5분 안에 페카 고분 도착/심층 던전 탭',
    '이동 후 5분 안에 {dungeonName} 도착 화면',
):
    if marker not in check:
        raise RuntimeError("V0.1.38 timeout marker missing: " + marker)

for forbidden in (
    'WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 30, ct)',
    'WaitForTargetAsync(arrivalTarget, 30, ct)',
    '이동 후 30초 안에 페카 고분',
    '이동 후 30초 안에 {dungeonName}',
):
    if forbidden in check:
        raise RuntimeError("old 30-second arrival timeout remains: " + forbidden)

if 'WaitForTargetAsync(slotTarget, 30, ct)' not in check:
    raise RuntimeError("30-second 1-1/2-1 slot wait missing")

ocr_check = read(ocr_path)
detector_check = read(detector_path)
targets_check = {x.get("Id"): x for x in json.loads(read(targets_path))}
if "FindCompactLabelAsync" not in ocr_check or "new[] { 1, 2, 3, 4 }" not in ocr_check:
    raise RuntimeError("compact label OCR retry scales missing")
for tid in ("route_d1_1", "route_d2_1", "route_regular_1_1", "route_regular_2_1"):
    if tid not in detector_check:
        raise RuntimeError("compact detector route missing: " + tid)
if targets_check["route_d1_1"].get("Text") != "1-1":
    raise RuntimeError("Peaca 1-1 tolerant text missing")
if targets_check["route_d2_1"].get("Text") != "2-1":
    raise RuntimeError("Peaca 2-1 tolerant text missing")
if targets_check["route_regular_1_1"].get("Text") != "1-1":
    raise RuntimeError("Runda/Fiod 1-1 tolerant text missing")
if targets_check["route_regular_2_1"].get("Text") != "2-1":
    raise RuntimeError("Runda/Fiod 2-1 tolerant text missing")

print("V0.1.38 patch applied: 5min arrival + Peaca/Runda/Fiod 1-1/2-1 compact OCR")
