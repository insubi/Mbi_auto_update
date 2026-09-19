using System.Diagnostics;

namespace DungeonVisionBot;

internal sealed partial class ScenarioEngine
{
    private bool IsAbyss => string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);
    private OcrRecognizer? _abyssResultOcr;
    private int AbyssCombatStepIndex
    {
        get
        {
            int index = _scenario.Steps.FindIndex(s => s.Target == "abyss_touch_screen");
            if (index < 0) throw new InvalidOperationException("어비스 전투 대기 단계가 없습니다.");
            return index;
        }
    }

    // Independent of normal-dungeon selected/challenge/retry targets and their ROIs.
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

    private async Task RetryAbyssResultAsync(CancellationToken ct)
    {
        if (!IsAbyss) throw new InvalidOperationException("어비스 결과 전용 처리입니다.");
        var timer = Stopwatch.StartNew();
        DetectionResult previous = DetectionResult.NotFound;
        while (timer.Elapsed < TimeSpan.FromSeconds(120))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var retry = await DetectAbyssResultRetryAsync(frame, ct);
            if (retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds))
            {
                ct.ThrowIfCancellationRequested();
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[어비스] 나가기/다시 하기/다른 던전 가기 2회 확인 -> 가운데 다시 하기 @ {retry.Center}");
                _input.ClickClientPoint(_hwnd, retry.Center);
                await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                await WaitForAbyssRetryTransitionAsync(ct);
                return;
            }
            previous = retry;
            // No monitors, alternate clicks or entry recovery while awaiting results.
            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }
        throw new InvalidOperationException("어비스 결과의 세 버튼을 확인하지 못해 정지합니다. 나가기/던전 선택으로 우회하지 않습니다.");
    }

    private async Task WaitForAbyssRetryTransitionAsync(CancellationToken ct)
    {
        var timer = Stopwatch.StartNew();
        int gone = 0;
        while (timer.Elapsed < TimeSpan.FromSeconds(30))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            // Check the retry label itself so a single missing companion label cannot authorize transition.
            var retry = await _abyssResultOcr!.FindCompactLabelAsync(frame, new Rectangle(Point.Empty, frame.Size), "다시 하기", ct);
            if (retry.Found) { gone = 0; }
            else
            {
                var enter = await _detector.DetectAsync("abyss_enter", frame, ct);
                if (enter.Found || await DetectAbyssOutsideWorkflowAsync(frame, ct))
                    throw new InvalidOperationException("어비스 다시 하기 후 예상과 다른 입장/필드 화면입니다. 추가 입력 없이 정지합니다.");
                if (++gone >= 3)
                {
                    Log?.Invoke("[어비스] 다시 하기 결과 화면 이탈 확인 -> 선택 화면 없이 전투 대기로 복귀");
                    return;
                }
            }
            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);
        }
        throw new InvalidOperationException("어비스 다시 하기 후 화면 전환을 확인하지 못했습니다. 중복 클릭 없이 정지합니다.");
    }
}
