#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
s = read(retry_path)

old_helpers = '''    private static readonly Rectangle AbyssRetrySafeRoi = new(280, 900, 240, 95);
    private static readonly Rectangle AbyssExitButtonRoi = new(160, 905, 180, 85);
    private static readonly Rectangle AbyssRetryButtonRoi = new(310, 905, 180, 85);
    private static readonly Rectangle AbyssOtherButtonRoi = new(460, 905, 180, 85);

    private static bool HasGreenButtonFill(Bitmap frame, Rectangle roi)
    {
        if (roi.Left < 0 || roi.Top < 0 || roi.Right > frame.Width || roi.Bottom > frame.Height)
            return false;

        int green = 0;
        int samples = 0;
        for (int y = roi.Top; y < roi.Bottom; y += 2)
        {
            for (int x = roi.Left; x < roi.Right; x += 2)
            {
                Color c = frame.GetPixel(x, y);
                samples++;
                if (c.G >= 85 && c.G >= c.R + 20 && c.G >= c.B + 10)
                    green++;
            }
        }

        return samples > 0 && green * 100 >= samples * 25;
    }

    private static bool HasAbyssResultButtonRow(Bitmap frame)
    {
        if (frame.Width != 800 || frame.Height != 1000)
            return false;

        return HasGreenButtonFill(frame, AbyssExitButtonRoi)
            && HasGreenButtonFill(frame, AbyssRetryButtonRoi)
            && HasGreenButtonFill(frame, AbyssOtherButtonRoi);
    }
'''
new_helpers = '''    private static readonly Rectangle AbyssRetrySafeRoi = new(280, 900, 240, 95);
    private static readonly Rectangle AbyssExitButtonRoi = new(160, 905, 180, 85);
    private static readonly Rectangle AbyssRetryButtonRoi = new(310, 905, 180, 85);
    private static readonly Rectangle AbyssOtherButtonRoi = new(460, 905, 180, 85);
    private string _lastAbyssResultDiagnostic = "no-frame";

    private static Rectangle ScaleAbyssResultRoi(Rectangle canonical, Size frameSize)
    {
        if (frameSize.Width <= 0 || frameSize.Height <= 0)
            return Rectangle.Empty;

        double sx = frameSize.Width / 800.0;
        double sy = frameSize.Height / 1000.0;
        var scaled = new Rectangle(
            (int)Math.Round(canonical.X * sx),
            (int)Math.Round(canonical.Y * sy),
            Math.Max(1, (int)Math.Round(canonical.Width * sx)),
            Math.Max(1, (int)Math.Round(canonical.Height * sy)));

        return Rectangle.Intersect(new Rectangle(Point.Empty, frameSize), scaled);
    }

    private static double GetGreenButtonRatio(Bitmap frame, Rectangle roi)
    {
        if (roi.Width <= 0 || roi.Height <= 0)
            return 0;

        int green = 0;
        int samples = 0;
        for (int y = roi.Top; y < roi.Bottom; y += 2)
        {
            for (int x = roi.Left; x < roi.Right; x += 2)
            {
                Color c = frame.GetPixel(x, y);
                samples++;

                // Allow both green and slightly cyan-tinted game buttons.
                if (c.G >= 70 && c.G >= c.R + 12 && c.G + 18 >= c.B)
                    green++;
            }
        }

        return samples == 0 ? 0 : green / (double)samples;
    }

    private bool TryDetectAbyssResultButtonRow(Bitmap frame, out Rectangle retryRoi)
    {
        retryRoi = Rectangle.Empty;

        double aspect = frame.Height == 0 ? 0 : frame.Width / (double)frame.Height;
        if (aspect < 0.74 || aspect > 0.86)
        {
            _lastAbyssResultDiagnostic = $"frame={frame.Width}x{frame.Height} aspect={aspect:0.000} outside-safe-range";
            return false;
        }

        var exit = ScaleAbyssResultRoi(AbyssExitButtonRoi, frame.Size);
        var retry = ScaleAbyssResultRoi(AbyssRetryButtonRoi, frame.Size);
        var other = ScaleAbyssResultRoi(AbyssOtherButtonRoi, frame.Size);

        double exitGreen = GetGreenButtonRatio(frame, exit);
        double retryGreen = GetGreenButtonRatio(frame, retry);
        double otherGreen = GetGreenButtonRatio(frame, other);

        _lastAbyssResultDiagnostic =
            $"frame={frame.Width}x{frame.Height} green(exit/retry/other)=" +
            $"{exitGreen:0.000}/{retryGreen:0.000}/{otherGreen:0.000}";

        // User result captures are around 0.48~0.52. Keep a comfortable margin for
        // compression/gamma differences while still requiring all three button regions.
        if (exitGreen < 0.18 || retryGreen < 0.18 || otherGreen < 0.18)
            return false;

        retryRoi = retry;
        return true;
    }
'''
if old_helpers not in s:
    raise SystemExit("V0.1.53 visual helper block not found")
s = s.replace(old_helpers, new_helpers, 1)

old_detect = '''        if (!IsAbyss) return DetectionResult.NotFound;
        if (frame.Width != 800 || frame.Height != 1000)
            return DetectionResult.NotFound;

        _abyssResultOcr ??= new OcrRecognizer();
        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, AbyssRetrySafeRoi, "다시 하기", ct);
        if (retry.Found && AbyssRetrySafeRoi.Contains(retry.Center))
            return retry;

        // OCR can miss the small white label on the bright green button. As a visual-only
        // fallback, require all three bottom green buttons in their canonical 800x1000 ROIs.
        // Only the middle ROI is ever returned/clicked.
        if (HasAbyssResultButtonRow(frame))
            return new DetectionResult(true, AbyssRetryButtonRoi, 0.95, "visual_result_button_row");

        return DetectionResult.NotFound;
'''
new_detect = '''        if (!IsAbyss) return DetectionResult.NotFound;

        double aspect = frame.Height == 0 ? 0 : frame.Width / (double)frame.Height;
        if (aspect < 0.74 || aspect > 0.86)
        {
            _lastAbyssResultDiagnostic = $"frame={frame.Width}x{frame.Height} aspect={aspect:0.000} outside-safe-range";
            return DetectionResult.NotFound;
        }

        _abyssResultOcr ??= new OcrRecognizer();
        var safeRetry = ScaleAbyssResultRoi(AbyssRetrySafeRoi, frame.Size);
        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, safeRetry, "다시 하기", ct);
        if (retry.Found && safeRetry.Contains(retry.Center))
        {
            _lastAbyssResultDiagnostic =
                $"frame={frame.Width}x{frame.Height} ocr=1 retry={retry.Bounds}";
            return retry;
        }

        // OCR can miss the small white label. Scale all canonical button ROIs to the
        // actual captured client size instead of requiring exactly 800x1000.
        if (TryDetectAbyssResultButtonRow(frame, out var visualRetry))
            return new DetectionResult(true, visualRetry, 0.95, "visual_result_button_row");

        return DetectionResult.NotFound;
'''
if old_detect not in s:
    raise SystemExit("V0.1.53 exact-size detector block not found")
s = s.replace(old_detect, new_detect, 1)

old_timeout = '        throw new InvalidOperationException("어비스 결과의 아래 중앙 다시 하기를 확인하지 못해 정지합니다. 나가기/다른 던전 가기로 우회하지 않습니다.");'
new_timeout = '        throw new InvalidOperationException($"어비스 결과의 아래 중앙 다시 하기를 확인하지 못해 정지합니다. 나가기/다른 던전 가기로 우회하지 않습니다. 진단: {_lastAbyssResultDiagnostic}");'
if old_timeout not in s:
    raise SystemExit("V0.1.53 retry timeout message not found")
s = s.replace(old_timeout, new_timeout, 1)

write(retry_path, s)

project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.54</Version>", "<Version>0.1.55</Version>"),
    ("<AssemblyVersion>0.1.54.0</AssemblyVersion>", "<AssemblyVersion>0.1.55.0</AssemblyVersion>"),
    ("<FileVersion>0.1.54.0</FileVersion>", "<FileVersion>0.1.55.0</FileVersion>"),
):
    if old in p:
        p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.54"' not in u:
    raise SystemExit("UpdateManager V0.1.54 marker missing")
u = u.replace('CurrentVersion = "V0.1.54"', 'CurrentVersion = "V0.1.55"', 1)
write(update, u)

t = read(retry_path)
required = (
    'ScaleAbyssResultRoi',
    'GetGreenButtonRatio',
    'aspect < 0.74 || aspect > 0.86',
    'green(exit/retry/other)',
    'exitGreen < 0.18 || retryGreen < 0.18 || otherGreen < 0.18',
    'FindCompactLabelAsync(frame, safeRetry, "다시 하기", ct)',
    'TryDetectAbyssResultButtonRow(frame, out var visualRetry)',
    '진단: {_lastAbyssResultDiagnostic}',
    '_input.ClickClientPoint(_hwnd, retry.Center);',
)
for marker in required:
    if marker not in t:
        raise SystemExit(f"required V0.1.55 marker missing: {marker}")

for forbidden in (
    'if (frame.Width != 800 || frame.Height != 1000)',
    'green * 100 >= samples * 25',
    'HasAbyssResultButtonRow(frame)',
):
    if forbidden in t:
        raise SystemExit(f"old brittle result detection remains: {forbidden}")

if "<Version>0.1.55</Version>" not in read(project):
    raise SystemExit("project version not V0.1.55")
if 'CurrentVersion = "V0.1.55"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.55")

print("V0.1.55 applied: Abyss result detection scales ROIs to actual capture size and logs diagnostics")
