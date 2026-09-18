#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0140_slot_hybrid_fix.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
matcher_path = app / "dungeon" / "TemplateMatcher.cs"
detector_path = app / "dungeon" / "TargetDetector.cs"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
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

# 1) Add a background-insensitive slot glyph matcher.
matcher = read(matcher_path)
anchor = '''    public DetectionResult FindMultiScale(
        Bitmap frame,
        Rectangle roi,
        string templatePath,
        double threshold,
        double minScale,
        double maxScale,
        double step)
    {
'''
if anchor not in matcher:
    raise RuntimeError("TemplateMatcher FindMultiScale anchor missing")

insert_before_end = '''        if (bestScore < threshold)
            return new DetectionResult(false, bounds, bestScore, null);
        return new DetectionResult(true, bounds, bestScore, null);
    }
}
'''
if insert_before_end not in matcher:
    raise RuntimeError("TemplateMatcher tail anchor missing")

slot_method = r'''
    public DetectionResult FindBrightGlyphMultiScale(
        Bitmap frame,
        Rectangle roi,
        string templatePath,
        double threshold,
        double minScale,
        double maxScale,
        double step)
    {
        string fullPath = Path.IsPathRooted(templatePath)
            ? templatePath
            : Path.Combine(_baseDir, templatePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(fullPath)) return DetectionResult.NotFound;
        if (frame.Width < 2 || frame.Height < 2) return DetectionResult.NotFound;

        Rectangle safeRoi = Rectangle.Intersect(
            new Rectangle(0, 0, frame.Width, frame.Height), roi);
        if (safeRoi.Width < 2 || safeRoi.Height < 2) return DetectionResult.NotFound;

        minScale = Math.Clamp(minScale, 0.50, 1.60);
        maxScale = Math.Clamp(maxScale, minScale, 1.60);
        step = Math.Clamp(step, 0.02, 0.20);

        using var frameMat = BitmapConverter.ToMat(frame);
        if (frameMat.Empty()) return DetectionResult.NotFound;

        using var frameGray = new Mat();
        if (frameMat.Channels() == 4)
            Cv2.CvtColor(frameMat, frameGray, ColorConversionCodes.BGRA2GRAY);
        else if (frameMat.Channels() == 3)
            Cv2.CvtColor(frameMat, frameGray, ColorConversionCodes.BGR2GRAY);
        else
            frameMat.CopyTo(frameGray);

        var cvRoi = new OpenCvSharp.Rect(safeRoi.X, safeRoi.Y, safeRoi.Width, safeRoi.Height);
        using var srcGray = new Mat(frameGray, cvRoi);
        using var tplGrayOriginal = Cv2.ImRead(fullPath, ImreadModes.Grayscale);
        if (tplGrayOriginal.Empty()) return DetectionResult.NotFound;

        double bestScore = double.MinValue;
        OpenCvSharp.Point bestLoc = default;
        int bestW = 0;
        int bestH = 0;

        // Dungeon labels are white pixel text over a translucent tile. Matching the
        // grayscale background made V0.1.39 sensitive to panel tint/selection state.
        // Sweep a few white-text thresholds and match only the binary glyph shape.
        foreach (double whiteThreshold in new[] { 130.0, 150.0, 170.0 })
        {
            using var srcBinary = new Mat();
            using var tplBinaryOriginal = new Mat();
            Cv2.Threshold(srcGray, srcBinary, whiteThreshold, 255, ThresholdTypes.Binary);
            Cv2.Threshold(tplGrayOriginal, tplBinaryOriginal, whiteThreshold, 255, ThresholdTypes.Binary);

            for (double scale = minScale; scale <= maxScale + 1e-9; scale += step)
            {
                int w = Math.Max(8, (int)Math.Round(tplBinaryOriginal.Width * scale));
                int h = Math.Max(8, (int)Math.Round(tplBinaryOriginal.Height * scale));
                if (w > srcBinary.Width || h > srcBinary.Height) continue;

                using var tplBinary = new Mat();
                if (w == tplBinaryOriginal.Width && h == tplBinaryOriginal.Height)
                    tplBinaryOriginal.CopyTo(tplBinary);
                else
                    Cv2.Resize(
                        tplBinaryOriginal,
                        tplBinary,
                        new OpenCvSharp.Size(w, h),
                        0,
                        0,
                        InterpolationFlags.Nearest);

                using var result = new Mat();
                Cv2.MatchTemplate(srcBinary, tplBinary, result, TemplateMatchModes.CCoeffNormed);
                Cv2.MinMaxLoc(result, out _, out double maxVal, out _, out OpenCvSharp.Point maxLoc);

                if (maxVal > bestScore)
                {
                    bestScore = maxVal;
                    bestLoc = maxLoc;
                    bestW = w;
                    bestH = h;
                }
            }
        }

        if (bestW <= 0 || bestH <= 0)
            return DetectionResult.NotFound;

        var bounds = new Rectangle(
            safeRoi.X + bestLoc.X,
            safeRoi.Y + bestLoc.Y,
            bestW,
            bestH);

        if (bestScore < threshold)
            return new DetectionResult(false, bounds, bestScore, null);
        return new DetectionResult(true, bounds, bestScore, null);
    }
'''
matcher = matcher.replace(insert_before_end, '''        if (bestScore < threshold)
            return new DetectionResult(false, bounds, bestScore, null);
        return new DetectionResult(true, bounds, bestScore, null);
    }
''' + slot_method + '''
}
''', 1)
write(matcher_path, matcher)

# 2) TargetDetector: strong binary-glyph visual match, exact compact OCR as backup.
detector = read(detector_path)
template_anchor = '''        if (t.Kind.Equals("template", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(t.TemplatePath)) return DetectionResult.NotFound;
            return _template.FindMultiScale(
                frame, roi, t.TemplatePath, t.Threshold,
                t.TemplateScaleMin, t.TemplateScaleMax, t.TemplateScaleStep);
        }

'''
if template_anchor not in detector:
    raise RuntimeError("TargetDetector template anchor missing")

slot_detector = r'''        if (t.Kind.Equals("slot-hybrid", StringComparison.OrdinalIgnoreCase))
        {
            DetectionResult visual = DetectionResult.NotFound;
            if (!string.IsNullOrWhiteSpace(t.TemplatePath))
            {
                visual = _template.FindBrightGlyphMultiScale(
                    frame, roi, t.TemplatePath, t.Threshold,
                    t.TemplateScaleMin, t.TemplateScaleMax, t.TemplateScaleStep);
            }

            // An exact OCR hit is always accepted. When the binary visual score is
            // already strong (>= threshold), OCR is only a confirmation attempt:
            // failure to OCR tiny pixel text does not discard the strong visual hit.
            if (!string.IsNullOrWhiteSpace(t.Text))
            {
                Rectangle ocrRoi = roi;
                if (visual.Bounds.Width > 0 && visual.Bounds.Height > 0)
                {
                    var expanded = Rectangle.Inflate(visual.Bounds, 26, 22);
                    ocrRoi = WindowCapture.ClampRoi(expanded, frame.Size);
                }

                var exactOcr = await _ocr.FindCompactLabelAsync(frame, ocrRoi, t.Text, ct);
                if (exactOcr.Found)
                {
                    if (visual.Found)
                        return new DetectionResult(true, visual.Bounds, visual.Score, exactOcr.ReadText);
                    return exactOcr;
                }
            }

            if (visual.Found)
                return visual;

            return visual;
        }

'''
detector = detector.replace(template_anchor, template_anchor + slot_detector, 1)
write(detector_path, detector)

# 3) Use the hybrid detector for every requested dungeon slot.
targets = json.loads(read(targets_path))
by_id = {t.get("Id"): t for t in targets}
slot_cfg = {
    "route_d1_1": {
        "Text": "D1-1",
        "Roi": {"X": 200, "Y": 440, "Width": 300, "Height": 180},
    },
    "route_d2_1": {
        "Text": "D2-1",
        "Roi": {"X": 200, "Y": 700, "Width": 320, "Height": 190},
    },
    "route_regular_1_1": {
        "Text": "1-1",
        "Roi": {"X": 180, "Y": 500, "Width": 360, "Height": 180},
    },
    "route_regular_2_1": {
        "Text": "2-1",
        "Roi": {"X": 200, "Y": 700, "Width": 360, "Height": 220},
    },
}
for tid, cfg in slot_cfg.items():
    if tid not in by_id:
        raise RuntimeError(f"slot target missing: {tid}")
    t = by_id[tid]
    t["Kind"] = "slot-hybrid"
    t["Text"] = cfg["Text"]
    t["Roi"] = cfg["Roi"]
    t["Threshold"] = 0.86
    t["TemplateScaleMin"] = 0.75
    t["TemplateScaleMax"] = 1.30
    t["TemplateScaleStep"] = 0.025
    t["MaxEditDistance"] = 0
    t["OcrRetryAt2x"] = True

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# 4) Preserve best failed score/bounds in runtime logs and error upload detail.
engine = read(engine_path)
engine = replace_once(
    engine,
    'var slot = await WaitForTargetAsync(slotTarget, 30, ct);',
    'var slot = await WaitForDungeonSlotAsync(slotTarget, 30, ct);',
    "slot wait call")
engine = replace_once(
    engine,
    'throw new TimeoutException($"{destination}의 {(d11 ? "1-1" : "2-1")} 표기를 30초 안에 찾지 못했습니다. 다른 구역을 대신 누르지 않습니다.");',
    'throw new TimeoutException($"{destination}의 {(d11 ? "1-1" : "2-1")} 표기를 30초 안에 찾지 못했습니다. best={slot.Score:0.000}, bounds={slot.Bounds}. 다른 구역을 대신 누르지 않습니다.");',
    "slot failure diagnostics")

wait_anchor = '''    private async Task<DetectionResult> WaitForTargetAsync(string targetId, int timeoutSeconds, CancellationToken ct)
    {
'''
if wait_anchor not in engine:
    raise RuntimeError("WaitForTargetAsync anchor missing")

slot_wait = r'''    private async Task<DetectionResult> WaitForDungeonSlotAsync(string targetId, int timeoutSeconds, CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        DetectionResult best = DetectionResult.NotFound;
        int attempt = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(timeoutSeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var r = await _detector.DetectAsync(targetId, frame, ct);
            attempt++;

            if (r.Score > best.Score)
                best = r;

            if (r.Found)
            {
                Log?.Invoke($"[던전 자동이동] 구역 검출 성공 target={targetId} · score={r.Score:0.000} · bounds={r.Bounds}" +
                    (string.IsNullOrWhiteSpace(r.ReadText) ? "" : $" · OCR=\"{r.ReadText}\""));
                return r;
            }

            if (attempt == 1 || attempt % 8 == 0)
                Log?.Invoke($"[던전 자동이동] 구역 탐색 target={targetId} · best={best.Score:0.000} · bounds={best.Bounds}");

            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        Log?.Invoke($"[던전 자동이동] 구역 탐색 타임아웃 target={targetId} · best={best.Score:0.000} · bounds={best.Bounds}");
        return best;
    }

'''
engine = engine.replace(wait_anchor, slot_wait + wait_anchor, 1)
write(engine_path, engine)

# 5) Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.39", "V0.1.40")
                   .replace("0.1.39.0", "0.1.40.0")
                   .replace("0.1.39", "0.1.40"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.40_SLOT_HYBRID_FIX.txt").write_text(
    "MABI AUTO V0.1.40 - DUNGEON SLOT HYBRID DETECTION\n\n"
    "Fixes the real V0.1.39 Peaca D2-1 miss.\n"
    "Peaca D1-1/D2-1 and Runda/Fiod 1-1/2-1 now use white-glyph binary OpenCV matching, wider search ROIs and 0.75-1.30 multi-scale search.\n"
    "Exact compact OCR is used as a secondary confirmation/fallback. Strong visual hits remain usable when Windows OCR cannot read tiny pixel text.\n"
    "Other slots (1-2/1-3/2-2/2-3) are never used as fallback choices.\n"
    "On failure the runtime log/error detail now includes the best visual score and bounds.\n"
    "V0.1.39 five-minute arrival wait, 30-second slot wait, purple dungeon-icon click, UI fix and updater survival are preserved.\n"
    "Automatic recovery is intentionally not added in this version.\n",
    encoding="utf-8"
)

# Structural verification.
matcher_check = read(matcher_path)
detector_check = read(detector_path)
engine_check = read(engine_path)
targets_check = {t.get("Id"): t for t in json.loads(read(targets_path))}

for marker in (
    "FindBrightGlyphMultiScale",
    "new[] { 130.0, 150.0, 170.0 }",
    "TemplateMatchModes.CCoeffNormed",
):
    if marker not in matcher_check:
        raise RuntimeError("binary glyph matcher marker missing: " + marker)

for marker in (
    't.Kind.Equals("slot-hybrid"',
    "FindCompactLabelAsync",
    "FindBrightGlyphMultiScale",
):
    if marker not in detector_check:
        raise RuntimeError("slot-hybrid detector marker missing: " + marker)

for tid in ("route_d1_1", "route_d2_1", "route_regular_1_1", "route_regular_2_1"):
    t = targets_check.get(tid)
    if t is None:
        raise RuntimeError("target missing after patch: " + tid)
    if t.get("Kind") != "slot-hybrid":
        raise RuntimeError(tid + " kind is not slot-hybrid")
    if float(t.get("Threshold", 0)) != 0.86:
        raise RuntimeError(tid + " threshold mismatch")
    if float(t.get("TemplateScaleMin", 0)) != 0.75 or float(t.get("TemplateScaleMax", 0)) != 1.30:
        raise RuntimeError(tid + " scale range mismatch")

for marker in (
    "WaitForDungeonSlotAsync(slotTarget, 30, ct)",
    "best={slot.Score:0.000}",
    "구역 탐색 타임아웃",
):
    if marker not in engine_check:
        raise RuntimeError("runtime slot diagnostics missing: " + marker)

if "WaitForTargetAsync(slotTarget, 30, ct)" in engine_check:
    raise RuntimeError("old generic slot wait remains")

print("V0.1.40 patch applied: binary glyph multi-scale + OCR backup for all Peaca/Runda/Fiod 1-1/2-1")
