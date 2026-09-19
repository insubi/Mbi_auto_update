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

anchor = "    private OcrRecognizer? _abyssResultOcr;\n"
insert = (
    "    private OcrRecognizer? _abyssResultOcr;\n"
    "    // 800x1000 client coordinates. Restrict result retry OCR to the middle bottom button only.\n"
    "    private static readonly Rectangle AbyssRetrySafeRoi = new(280, 900, 240, 95);\n"
)
if anchor not in s:
    raise SystemExit("Abyss result OCR anchor missing")
s = s.replace(anchor, insert, 1)

old_detect = '''    // Independent of normal-dungeon selected/challenge/retry targets and their ROIs.
    private async Task<DetectionResult> DetectAbyssResultRetryAsync(Bitmap frame, CancellationToken ct)
    {
        if (!IsAbyss) return DetectionResult.NotFound;
        _abyssResultOcr ??= new OcrRecognizer();
        var client = new Rectangle(Point.Empty, frame.Size);
        var exit = await _abyssResultOcr.FindCompactLabelAsync(frame, client, "나가기", ct);
        if (!exit.Found) return DetectionResult.NotFound;
        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, client, "다시 하기", ct);
        if (!retry.Found) return DetectionResult.NotFound;
        var other = await _abyssResultOcr.FindCompactLabelAsync(frame, client, "다른 던전 가기", ct);
        if (!other.Found) return DetectionResult.NotFound;
        // The three distinct labels must appear in left/centre/right order on the same row.
        if (!AbyssResultLayout.IsConfirmed(exit.Bounds, retry.Bounds, other.Bounds))
            return DetectionResult.NotFound;
        return retry;
    }
'''
new_detect = '''    // Independent of normal-dungeon selected/challenge/retry targets and their ROIs.
    // Result screens are allowed to continue only when the exact middle-bottom retry label
    // is found inside its fixed safe ROI on the canonical 800x1000 client.
    private async Task<DetectionResult> DetectAbyssResultRetryAsync(Bitmap frame, CancellationToken ct)
    {
        if (!IsAbyss) return DetectionResult.NotFound;
        if (frame.Width != 800 || frame.Height != 1000)
            return DetectionResult.NotFound;

        _abyssResultOcr ??= new OcrRecognizer();
        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, AbyssRetrySafeRoi, "다시 하기", ct);
        if (!retry.Found || !AbyssRetrySafeRoi.Contains(retry.Center))
            return DetectionResult.NotFound;

        return retry;
    }
'''
if old_detect not in s:
    raise SystemExit("old three-button Abyss result detector block missing")
s = s.replace(old_detect, new_detect, 1)

old_log = '                Log?.Invoke($"[어비스] 나가기/다시 하기/다른 던전 가기 2회 확인 -> 가운데 다시 하기 @ {retry.Center}");'
new_log = '                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} safe={AbyssRetrySafeRoi}");'
if old_log not in s:
    raise SystemExit("old three-button confirmation log missing")
s = s.replace(old_log, new_log, 1)

old_timeout = '        throw new InvalidOperationException("어비스 결과의 세 버튼을 확인하지 못해 정지합니다. 나가기/던전 선택으로 우회하지 않습니다.");'
new_timeout = '        throw new InvalidOperationException("어비스 결과의 아래 중앙 다시 하기를 확인하지 못해 정지합니다. 나가기/다른 던전 가기로 우회하지 않습니다.");'
if old_timeout not in s:
    raise SystemExit("old Abyss result timeout message missing")
s = s.replace(old_timeout, new_timeout, 1)

old_transition = '            var retry = await _abyssResultOcr!.FindCompactLabelAsync(frame, new Rectangle(Point.Empty, frame.Size), "다시 하기", ct);'
new_transition = '''            var retry = frame.Width == 800 && frame.Height == 1000
                ? await _abyssResultOcr!.FindCompactLabelAsync(frame, AbyssRetrySafeRoi, "다시 하기", ct)
                : DetectionResult.NotFound;'''
if old_transition not in s:
    raise SystemExit("old retry transition OCR line missing")
s = s.replace(old_transition, new_transition, 1)

write(retry_path, s)

# Narrow metadata-only version bump.
project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.51</Version>", "<Version>0.1.52</Version>"),
    ("<AssemblyVersion>0.1.51.0</AssemblyVersion>", "<AssemblyVersion>0.1.52.0</AssemblyVersion>"),
    ("<FileVersion>0.1.51.0</FileVersion>", "<FileVersion>0.1.52.0</FileVersion>"),
):
    if old in p:
        p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.51"' not in u:
    raise SystemExit("UpdateManager V0.1.51 marker missing")
u = u.replace('CurrentVersion = "V0.1.51"', 'CurrentVersion = "V0.1.52"', 1)
write(update, u)

# Safety invariants.
t = read(retry_path)
required = (
    'private static readonly Rectangle AbyssRetrySafeRoi = new(280, 900, 240, 95);',
    'frame.Width != 800 || frame.Height != 1000',
    'FindCompactLabelAsync(frame, AbyssRetrySafeRoi, "다시 하기", ct)',
    'retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds)',
    '_input.ClickClientPoint(_hwnd, retry.Center);',
    '다시 하기만 클릭',
)
for marker in required:
    if marker not in t:
        raise SystemExit(f"required V0.1.52 retry invariant missing: {marker}")

for forbidden in (
    'FindCompactLabelAsync(frame, client, "나가기", ct)',
    'FindCompactLabelAsync(frame, client, "다른 던전 가기", ct)',
    'AbyssResultLayout.IsConfirmed(exit.Bounds, retry.Bounds, other.Bounds)',
):
    if forbidden in t:
        raise SystemExit(f"old three-button gate remains: {forbidden}")

if "<Version>0.1.52</Version>" not in read(project):
    raise SystemExit("project version not V0.1.52")
if 'CurrentVersion = "V0.1.52"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.52")

print("V0.1.52 applied: Abyss result retry uses strict center-bottom retry ROI with 2-frame confirmation")
