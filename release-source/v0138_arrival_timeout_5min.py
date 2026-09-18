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

# All requested dungeon slots use a dedicated exact compact-label OCR path.
# Important: do NOT use fuzzy matching here, because D1-2/D1-3/D2-2/D2-3 must never
# be accepted in place of the requested 1-1/2-1 slot.
ocr = read(ocr_path)
ocr_anchor = '''    public async Task<DetectionResult> FindTextAsync(Bitmap frame, Rectangle roi, string wanted, int maxEditDistance, bool retry2x, CancellationToken ct)
    {
        var result = await FindAtScaleAsync(frame, roi, wanted, maxEditDistance, 1, ct);
        if (result.Found || !retry2x) return result;
        return await FindAtScaleAsync(frame, roi, wanted, maxEditDistance, 2, ct);
    }
'''
ocr_insert = ocr_anchor + '''
    public async Task<DetectionResult> FindCompactLabelAsync(Bitmap frame, Rectangle roi, string wanted, CancellationToken ct)
    {
        foreach (int scale in new[] { 1, 2, 3, 4 })
        {
            var result = await FindExactCompactAtScaleAsync(frame, roi, wanted, scale, ct);
            if (result.Found) return result;
        }
        return DetectionResult.NotFound;
    }

    private async Task<DetectionResult> FindExactCompactAtScaleAsync(Bitmap frame, Rectangle roi, string wanted, int scale, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        using var crop = frame.Clone(roi, PixelFormat.Format24bppRgb);
        using var prepared = scale == 1 ? (Bitmap)crop.Clone() : ResizeNearest(crop, crop.Width * scale, crop.Height * scale);
        using var software = await ToSoftwareBitmapAsync(prepared);
        var ocr = await _engine.RecognizeAsync(software);
        ct.ThrowIfCancellationRequested();

        string wantedNorm = FuzzyText.Normalize(wanted);
        foreach (var line in ocr.Lines)
        {
            var words = line.Words;
            for (int start = 0; start < words.Count; start++)
            {
                for (int count = 1; count <= 3 && start + count <= words.Count; count++)
                {
                    var selected = words.Skip(start).Take(count).ToArray();
                    string candidate = string.Concat(selected.Select(w => w.Text));
                    if (!FuzzyText.Normalize(candidate).Equals(wantedNorm, StringComparison.OrdinalIgnoreCase))
                        continue;

                    double left = selected.Min(w => w.BoundingRect.X);
                    double top = selected.Min(w => w.BoundingRect.Y);
                    double right = selected.Max(w => w.BoundingRect.X + w.BoundingRect.Width);
                    double bottom = selected.Max(w => w.BoundingRect.Y + w.BoundingRect.Height);
                    var bounds = Rectangle.FromLTRB(
                        roi.X + (int)Math.Round(left / scale),
                        roi.Y + (int)Math.Round(top / scale),
                        roi.X + (int)Math.Round(right / scale),
                        roi.Y + (int)Math.Round(bottom / scale));
                    return new DetectionResult(true, bounds, 1.0, candidate);
                }
            }
        }
        return DetectionResult.NotFound;
    }
'''
ocr = replace_once(ocr, ocr_anchor, ocr_insert, "exact compact label OCR")
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

            bool exactDungeonSlot =
                id.Equals("route_d1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_d2_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_1_1", StringComparison.OrdinalIgnoreCase) ||
                id.Equals("route_regular_2_1", StringComparison.OrdinalIgnoreCase);

            if (exactDungeonSlot)
                return await _ocr.FindCompactLabelAsync(frame, roi, t.Text, ct);

            return await _ocr.FindTextAsync(frame, roi, t.Text, t.MaxEditDistance, t.OcrRetryAt2x, ct);
        }
'''
detector = replace_once(detector, detector_anchor, detector_new, "exact dungeon slot detector")
write(detector_path, detector)

# Narrow ROIs to the actual 1-1/2-1 tile locations so adjacent slots are excluded.
# Peaca uses D1-1/D2-1 labels. Runda/Fiod use plain 1-1/2-1 labels.
import json
targets = json.loads(read(targets_path))
slot_updates = {
    "route_d1_1": {
        "Roi": {"X": 255, "Y": 470, "Width": 125, "Height": 125},
        "Text": "D1-1",
        "MaxEditDistance": 0,
        "OcrRetryAt2x": True,
    },
    "route_d2_1": {
        "Roi": {"X": 255, "Y": 760, "Width": 125, "Height": 135},
        "Text": "D2-1",
        "MaxEditDistance": 0,
        "OcrRetryAt2x": True,
    },
    "route_regular_1_1": {
        "Roi": {"X": 255, "Y": 540, "Width": 125, "Height": 125},
        "Text": "1-1",
        "MaxEditDistance": 0,
        "OcrRetryAt2x": True,
    },
    "route_regular_2_1": {
        "Roi": {"X": 300, "Y": 760, "Width": 125, "Height": 135},
        "Text": "2-1",
        "MaxEditDistance": 0,
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

# Give all selected 1-1/2-1 labels up to 30 seconds to settle/become readable.
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
    "Peaca/Runda/Fiod 1-1 and 2-1 markers use narrow per-layout ROIs plus exact compact-label OCR at 1x/2x/3x/4x.\n"
    "Peaca requires exact D1-1/D2-1; Runda/Fiod require exact 1-1/2-1. Adjacent slots are excluded.\n"
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
if "FindCompactLabelAsync" not in ocr_check or "FindExactCompactAtScaleAsync" not in ocr_check:
    raise RuntimeError("exact compact label OCR missing")
if "new[] { 1, 2, 3, 4 }" not in ocr_check:
    raise RuntimeError("compact OCR scale retries missing")
for tid in ("route_d1_1", "route_d2_1", "route_regular_1_1", "route_regular_2_1"):
    if tid not in detector_check:
        raise RuntimeError("exact detector route missing: " + tid)
expected_slots = {
    "route_d1_1": ("D1-1", 0),
    "route_d2_1": ("D2-1", 0),
    "route_regular_1_1": ("1-1", 0),
    "route_regular_2_1": ("2-1", 0),
}
for tid, (wanted, distance) in expected_slots.items():
    if targets_check[tid].get("Text") != wanted or targets_check[tid].get("MaxEditDistance") != distance:
        raise RuntimeError("unsafe slot target config: " + tid)
if 'AddButton("인식 테스트", new(18, 511, 178, 59), owner.ShowVisualRecognitionTest, "", "nav");' not in read(app / "MainForm.ReferenceUI.cs"):
    raise RuntimeError("V0.1.37 recognition-test UI fix not preserved")

print("V0.1.38 patch applied: 5min arrival + exact Peaca/Runda/Fiod 1-1/2-1 OCR")
