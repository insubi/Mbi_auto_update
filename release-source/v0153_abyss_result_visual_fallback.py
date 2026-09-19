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

anchor = '    private static readonly Rectangle AbyssRetrySafeRoi = new(280, 900, 240, 95);\n'
replacement = '''    private static readonly Rectangle AbyssRetrySafeRoi = new(280, 900, 240, 95);
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
if anchor not in s:
    raise SystemExit("V0.1.52 retry ROI anchor missing")
s = s.replace(anchor, replacement, 1)

old_detect_tail = '''        _abyssResultOcr ??= new OcrRecognizer();
        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, AbyssRetrySafeRoi, "다시 하기", ct);
        if (!retry.Found || !AbyssRetrySafeRoi.Contains(retry.Center))
            return DetectionResult.NotFound;

        return retry;
    }
'''
new_detect_tail = '''        _abyssResultOcr ??= new OcrRecognizer();
        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, AbyssRetrySafeRoi, "다시 하기", ct);
        if (retry.Found && AbyssRetrySafeRoi.Contains(retry.Center))
            return retry;

        // OCR can miss the small white label on the bright green button. As a visual-only
        // fallback, require all three bottom green buttons in their canonical 800x1000 ROIs.
        // Only the middle ROI is ever returned/clicked.
        if (HasAbyssResultButtonRow(frame))
            return new DetectionResult(true, AbyssRetryButtonRoi, 0.95, "visual_result_button_row");

        return DetectionResult.NotFound;
    }
'''
if old_detect_tail not in s:
    raise SystemExit("V0.1.52 retry detector tail missing")
s = s.replace(old_detect_tail, new_detect_tail, 1)

old_log = '                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} safe={AbyssRetrySafeRoi}");'
new_log = '                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");'
if old_log not in s:
    raise SystemExit("V0.1.52 retry click log missing")
s = s.replace(old_log, new_log, 1)

old_transition = '''            var retry = frame.Width == 800 && frame.Height == 1000
                ? await _abyssResultOcr!.FindCompactLabelAsync(frame, AbyssRetrySafeRoi, "다시 하기", ct)
                : DetectionResult.NotFound;
            if (retry.Found) { gone = 0; }
'''
new_transition = '''            var retry = await DetectAbyssResultRetryAsync(frame, ct);
            if (retry.Found) { gone = 0; }
'''
if old_transition not in s:
    raise SystemExit("V0.1.52 transition retry check missing")
s = s.replace(old_transition, new_transition, 1)

write(retry_path, s)

project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.52</Version>", "<Version>0.1.53</Version>"),
    ("<AssemblyVersion>0.1.52.0</AssemblyVersion>", "<AssemblyVersion>0.1.53.0</AssemblyVersion>"),
    ("<FileVersion>0.1.52.0</FileVersion>", "<FileVersion>0.1.53.0</FileVersion>"),
):
    if old in p:
        p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.52"' not in u:
    raise SystemExit("UpdateManager V0.1.52 marker missing")
u = u.replace('CurrentVersion = "V0.1.52"', 'CurrentVersion = "V0.1.53"', 1)
write(update, u)

t = read(retry_path)
required = (
    'private static readonly Rectangle AbyssExitButtonRoi = new(160, 905, 180, 85);',
    'private static readonly Rectangle AbyssRetryButtonRoi = new(310, 905, 180, 85);',
    'private static readonly Rectangle AbyssOtherButtonRoi = new(460, 905, 180, 85);',
    'green * 100 >= samples * 25',
    'HasAbyssResultButtonRow(frame)',
    'new DetectionResult(true, AbyssRetryButtonRoi, 0.95, "visual_result_button_row")',
    'var retry = await DetectAbyssResultRetryAsync(frame, ct);',
    '_input.ClickClientPoint(_hwnd, retry.Center);',
)
for marker in required:
    if marker not in t:
        raise SystemExit(f"required V0.1.53 marker missing: {marker}")

if "<Version>0.1.53</Version>" not in read(project):
    raise SystemExit("project version not V0.1.53")
if 'CurrentVersion = "V0.1.53"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.53")

print("V0.1.53 applied: Abyss result retry gains 3-green-button visual fallback")
