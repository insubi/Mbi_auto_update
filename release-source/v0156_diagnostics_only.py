#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

# ---------------------------------------------------------------------------
# 1) Add a diagnostics-only partial class.
#    It never makes click/detection/transition decisions.
# ---------------------------------------------------------------------------
diag = app / "dungeon" / "ScenarioEngine.Diagnostics.cs"
diag.write_text(r'''using System.Drawing;
using System.Drawing.Imaging;

namespace DungeonVisionBot;

internal sealed partial class ScenarioEngine
{
    private readonly object _diagnosticLock = new();
    private readonly Queue<Bitmap> _diagnosticFrames = new();
    private long _diagnosticLastFrameSampleTick;
    private string _diagnosticStage = "init";
    private string _diagnosticPreviousStage = "init";
    private string _diagnosticLastDetection = "none";
    private string _diagnosticLastOcr = "none";
    private string _diagnosticLastScore = "n/a";
    private string _diagnosticLastBounds = "n/a";
    private string _diagnosticLastClick = "none";
    private string _diagnosticLastTransition = "init";
    private string _diagnosticFrameSize = "unknown";

    private void DiagnosticSetStage(string target, string name)
    {
        if (!IsAbyss) return;

        string next = $"{target} | {name}";
        string? transition = null;
        lock (_diagnosticLock)
        {
            if (!string.Equals(_diagnosticStage, next, StringComparison.Ordinal))
            {
                _diagnosticPreviousStage = _diagnosticStage;
                _diagnosticStage = next;
                _diagnosticLastTransition = $"{_diagnosticPreviousStage} -> {_diagnosticStage}";
                transition = _diagnosticLastTransition;
            }
        }

        if (transition is not null)
            Log?.Invoke($"[진단] 어비스 상태 전환: {transition}");
    }

    private void DiagnosticObserveFrame(Bitmap frame)
    {
        if (!IsAbyss) return;

        long now = Environment.TickCount64;
        lock (_diagnosticLock)
        {
            _diagnosticFrameSize = $"{frame.Width}x{frame.Height}";

            // Keep five recent sampled frames in memory. Sampling prevents diagnostics
            // from changing the normal detector/click timing materially.
            if (_diagnosticLastFrameSampleTick != 0 &&
                now - _diagnosticLastFrameSampleTick < 500)
                return;

            _diagnosticLastFrameSampleTick = now;
            Bitmap copy = (Bitmap)frame.Clone();
            _diagnosticFrames.Enqueue(copy);
            while (_diagnosticFrames.Count > 5)
            {
                Bitmap old = _diagnosticFrames.Dequeue();
                old.Dispose();
            }
        }
    }

    private void DiagnosticObserveDetection(string id, DetectionResult result)
    {
        if (!IsAbyss) return;

        lock (_diagnosticLock)
        {
            _diagnosticLastDetection = $"{id}: found={(result.Found ? 1 : 0)}";
            _diagnosticLastOcr = string.IsNullOrWhiteSpace(result.ReadText) ? "none" : result.ReadText!;
            _diagnosticLastScore = result.Score.ToString("0.000");
            _diagnosticLastBounds = result.Bounds.ToString();
        }
    }

    private void DiagnosticObserveClick(string reason, Point point)
    {
        if (!IsAbyss) return;

        lock (_diagnosticLock)
            _diagnosticLastClick = $"{reason} @ {point.X},{point.Y}";

        Log?.Invoke($"[진단] 최근 어비스 클릭: {_diagnosticLastClick}");
    }

    private string DiagnosticSummary()
    {
        lock (_diagnosticLock)
        {
            return
                $"stage={_diagnosticStage}; " +
                $"transition={_diagnosticLastTransition}; " +
                $"frame={_diagnosticFrameSize}; " +
                $"detect={_diagnosticLastDetection}; " +
                $"ocr={_diagnosticLastOcr}; " +
                $"score={_diagnosticLastScore}; " +
                $"bounds={_diagnosticLastBounds}; " +
                $"click={_diagnosticLastClick}";
        }
    }

    private void DiagnosticPersistFailure(string label)
    {
        if (!IsAbyss) return;

        try
        {
            string dir = Path.Combine(_baseDir, "debug");
            Directory.CreateDirectory(dir);
            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss_fff");
            string safeLabel = Safe(label);

            List<Bitmap> snapshots;
            string summary;
            lock (_diagnosticLock)
            {
                snapshots = _diagnosticFrames.Select(f => (Bitmap)f.Clone()).ToList();
                summary = DiagnosticSummaryUnsafe();
            }

            for (int i = 0; i < snapshots.Count; i++)
            {
                using Bitmap shot = snapshots[i];
                string path = Path.Combine(dir, $"diag_{stamp}_{safeLabel}_before_{snapshots.Count - i}.png");
                shot.Save(path, ImageFormat.Png);
            }

            File.WriteAllText(
                Path.Combine(dir, $"diag_{stamp}_{safeLabel}.txt"),
                summary,
                System.Text.Encoding.UTF8);

            PruneDebugScreenshots();
            Log?.Invoke($"[진단] 실패 직전 프레임 {snapshots.Count}장 저장 · {summary}");
        }
        catch (Exception ex)
        {
            // Diagnostics must never change automation behavior.
            Log?.Invoke($"[진단] 실패 정보 저장 중 예외(동작에는 영향 없음): {ex.Message}");
        }
    }

    private string DiagnosticSummaryUnsafe()
    {
        return
            $"stage={_diagnosticStage}; " +
            $"transition={_diagnosticLastTransition}; " +
            $"frame={_diagnosticFrameSize}; " +
            $"detect={_diagnosticLastDetection}; " +
            $"ocr={_diagnosticLastOcr}; " +
            $"score={_diagnosticLastScore}; " +
            $"bounds={_diagnosticLastBounds}; " +
            $"click={_diagnosticLastClick}";
    }
}
''', encoding="utf-8", newline="\n")

# ---------------------------------------------------------------------------
# 2) Instrument ScenarioEngine.cs without changing any decision condition.
# ---------------------------------------------------------------------------
engine = app / "dungeon" / "ScenarioEngine.cs"
s = read(engine)

old = '''                while (!recovered)
                {
                    recoveryFailures++;
                    Log?.Invoke($"[자동복구] {recoveryFailures}/{max} 단계 시간초과: {ex.Message}");
                    await SaveRecoveryScreenshotAsync($"recovery_{recoveryFailures}", ct);
'''
new = '''                while (!recovered)
                {
                    recoveryFailures++;
                    Log?.Invoke($"[자동복구] {recoveryFailures}/{max} 단계 시간초과: {ex.Message}");
                    if (IsAbyss)
                    {
                        Log?.Invoke($"[진단] {DiagnosticSummary()}");
                        DiagnosticPersistFailure($"timeout_step_{_currentStepIndex + 1}_attempt_{recoveryFailures}");
                    }
                    await SaveRecoveryScreenshotAsync($"recovery_{recoveryFailures}", ct);
'''
if old not in s:
    raise SystemExit("timeout recovery anchor missing")
s = s.replace(old, new, 1)

old = '''    private async Task ExecuteStepAsync(ScenarioStep step, CancellationToken ct)
    {
        if (IsAbyss && step.Target == "abyss_result_retry")
'''
new = '''    private async Task ExecuteStepAsync(ScenarioStep step, CancellationToken ct)
    {
        DiagnosticSetStage(step.Target, step.Name);

        if (IsAbyss && step.Target == "abyss_result_retry")
'''
if old not in s:
    raise SystemExit("ExecuteStepAsync anchor missing")
s = s.replace(old, new, 1)

# Record the main step detector result immediately before the existing decision.
old = '''            if (found.Found)
            {
                Log?.Invoke($"[{step.Name}] 발견: {found.ReadText ?? found.Score.ToString("0.000")} @ {found.Bounds}");
'''
new = '''            DiagnosticObserveDetection(step.Target, found);

            if (found.Found)
            {
                Log?.Invoke($"[{step.Name}] 발견: {found.ReadText ?? found.Score.ToString("0.000")} @ {found.Bounds}");
'''
if old not in s:
    raise SystemExit("main found decision anchor missing")
s = s.replace(old, new, 1)

# Observe clear detectors without changing their boolean rule.
old = '''    private async Task<DetectionResult> DetectAbyssConfirmedClearAsync(Bitmap frame, CancellationToken ct)
    {
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        if (clearTitle.Found && touch.Found)
'''
new = '''    private async Task<DetectionResult> DetectAbyssConfirmedClearAsync(Bitmap frame, CancellationToken ct)
    {
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        DiagnosticObserveDetection("abyss_dungeon_clear_visual", clearTitle);
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        DiagnosticObserveDetection("abyss_touch_screen", touch);
        if (clearTitle.Found && touch.Found)
'''
if old not in s:
    raise SystemExit("DetectAbyssConfirmedClearAsync anchor missing")
s = s.replace(old, new, 1)

# Record the already-decided clear-screen click point.
old = '''        Log?.Invoke($"[어비스] 확인된 '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds} source={touch.ReadText}");
        _input.ClickClientPoint(_hwnd, touch.Center);
'''
new = '''        Log?.Invoke($"[어비스] 확인된 '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds} source={touch.ReadText}");
        DiagnosticObserveClick("abyss_clear_touch", touch.Center);
        _input.ClickClientPoint(_hwnd, touch.Center);
'''
if old not in s:
    raise SystemExit("clear touch click anchor missing")
s = s.replace(old, new, 1)

# Observe each successful frame capture; returned Bitmap and retry behavior are unchanged.
old = '''            try
            {
                return _capture.CaptureClient(_hwnd);
            }
'''
new = '''            try
            {
                Bitmap frame = _capture.CaptureClient(_hwnd);
                DiagnosticObserveFrame(frame);
                return frame;
            }
'''
if old not in s:
    raise SystemExit("CaptureGameWindowAsync return anchor missing")
s = s.replace(old, new, 1)

write(engine, s)

# ---------------------------------------------------------------------------
# 3) Instrument AbyssRetry only. Keep all V0.1.55 conditions/click decisions intact.
# ---------------------------------------------------------------------------
retry = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
r = read(retry)

old = '''        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, safeRetry, "다시 하기", ct);
        if (retry.Found && safeRetry.Contains(retry.Center))
'''
new = '''        var retry = await _abyssResultOcr.FindCompactLabelAsync(frame, safeRetry, "다시 하기", ct);
        DiagnosticObserveDetection("abyss_result_retry_ocr", retry);
        if (retry.Found && safeRetry.Contains(retry.Center))
'''
if old not in r:
    raise SystemExit("retry OCR anchor missing")
r = r.replace(old, new, 1)

old = '''        if (TryDetectAbyssResultButtonRow(frame, out var visualRetry))
            return new DetectionResult(true, visualRetry, 0.95, "visual_result_button_row");

        return DetectionResult.NotFound;
'''
new = '''        if (TryDetectAbyssResultButtonRow(frame, out var visualRetry))
        {
            var visual = new DetectionResult(true, visualRetry, 0.95, "visual_result_button_row");
            DiagnosticObserveDetection("abyss_result_visual_row", visual);
            return visual;
        }

        DiagnosticObserveDetection("abyss_result_visual_row", DetectionResult.NotFound);
        return DetectionResult.NotFound;
'''
if old not in r:
    raise SystemExit("retry visual fallback anchor missing")
r = r.replace(old, new, 1)

old = '''                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");
                _input.ClickClientPoint(_hwnd, retry.Center);
'''
new = '''                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");
                DiagnosticObserveClick("abyss_result_retry", retry.Center);
                _input.ClickClientPoint(_hwnd, retry.Center);
'''
if old not in r:
    raise SystemExit("retry click anchor missing")
r = r.replace(old, new, 1)

old = '''        throw new InvalidOperationException($"어비스 결과의 아래 중앙 다시 하기를 확인하지 못해 정지합니다. 나가기/다른 던전 가기로 우회하지 않습니다. 진단: {_lastAbyssResultDiagnostic}");
'''
new = '''        DiagnosticPersistFailure("abyss_result_retry_timeout");
        throw new InvalidOperationException(
            $"어비스 결과의 아래 중앙 다시 하기를 확인하지 못해 정지합니다. " +
            $"나가기/다른 던전 가기로 우회하지 않습니다. 진단: {_lastAbyssResultDiagnostic}; {DiagnosticSummary()}");
'''
if old not in r:
    raise SystemExit("retry timeout anchor missing")
r = r.replace(old, new, 1)

write(retry, r)

# ---------------------------------------------------------------------------
# 4) Metadata-only version bump.
# ---------------------------------------------------------------------------
project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.55</Version>", "<Version>0.1.56</Version>"),
    ("<AssemblyVersion>0.1.55.0</AssemblyVersion>", "<AssemblyVersion>0.1.56.0</AssemblyVersion>"),
    ("<FileVersion>0.1.55.0</FileVersion>", "<FileVersion>0.1.56.0</FileVersion>"),
):
    if old not in p:
        raise SystemExit(f"project version marker missing: {old}")
    p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.55"' not in u:
    raise SystemExit("UpdateManager V0.1.55 marker missing")
u = u.replace('CurrentVersion = "V0.1.55"', 'CurrentVersion = "V0.1.56"', 1)
write(update, u)

# ---------------------------------------------------------------------------
# 5) Invariants: diagnostics only; V0.1.55 decisions must remain present.
# ---------------------------------------------------------------------------
engine_text = read(engine)
retry_text = read(retry)
diag_text = read(diag)

required_diag = (
    'Queue<Bitmap> _diagnosticFrames',
    'while (_diagnosticFrames.Count > 5)',
    'now - _diagnosticLastFrameSampleTick < 500',
    'DiagnosticPersistFailure',
    'DiagnosticSummary',
    '[진단] 어비스 상태 전환',
    'diag_{stamp}_{safeLabel}_before_',
)
for marker in required_diag:
    if marker not in diag_text:
        raise SystemExit(f"diagnostic marker missing: {marker}")

required_v0155 = (
    'ScaleAbyssResultRoi',
    'GetGreenButtonRatio',
    'aspect < 0.74 || aspect > 0.86',
    'exitGreen < 0.18 || retryGreen < 0.18 || otherGreen < 0.18',
    'retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds)',
    '_input.ClickClientPoint(_hwnd, retry.Center);',
)
for marker in required_v0155:
    if marker not in retry_text:
        raise SystemExit(f"V0.1.55 retry behavior missing: {marker}")

required_v0154 = (
    'missing clear/touch templates is NOT treated as a successful',
    'Step 5 is not complete until the actual result screen is confirmed.',
    '어비스 클리어 화면 클릭 후 실제 결과 화면을 30초 안에 확인하지 못했습니다.',
)
for marker in required_v0154:
    if marker not in engine_text:
        raise SystemExit(f"V0.1.54 clear-transition behavior missing: {marker}")

if "<Version>0.1.56</Version>" not in read(project):
    raise SystemExit("project version not V0.1.56")
if 'CurrentVersion = "V0.1.56"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.56")

print("V0.1.56 applied: diagnostics only; automation decisions unchanged")
