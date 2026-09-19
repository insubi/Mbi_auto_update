using System.Diagnostics;

namespace DungeonVisionBot;

internal sealed partial class ScenarioEngine
{
    private bool IsAbyss => string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);
    private OcrRecognizer? _abyssResultOcr;
    // 800x1000 client coordinates. Restrict result retry OCR to the middle bottom button only.
    private static readonly Rectangle AbyssRetrySafeRoi = new(280, 900, 240, 95);
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
    // Clear animation and result buttons share the bottom of the client.
    // Require title AND prompt, and return the detected prompt, never a guessed point.
    private async Task<DetectionResult> DetectAbyssClearPromptAsync(Bitmap frame, CancellationToken ct)
    {
        if (!IsAbyss || frame.Width != 800 || frame.Height != 1000)
            return DetectionResult.NotFound;
        var titleRoi = new Rectangle(120, 120, 560, 300);
        var promptRoi = new Rectangle(160, 870, 480, 125);
        var title = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        if (!title.Found || !titleRoi.Contains(title.Center))
        {
            _abyssResultOcr ??= new OcrRecognizer();
            title = await _abyssResultOcr.FindTextAsync(frame, titleRoi, "던전 클리어", 0, true, ct);
        }
        if (!title.Found) return DetectionResult.NotFound;

        var prompt = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        if (prompt.Found && promptRoi.Contains(prompt.Center)) return prompt;
        _abyssResultOcr ??= new OcrRecognizer();
        return await _abyssResultOcr.FindTextAsync(frame, promptRoi, "화면을 터치해 주세요", 0, true, ct);
    }

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
    // Result screens are allowed to continue only when the exact middle-bottom retry label
    // is found inside its fixed safe ROI on the canonical 800x1000 client.
    private async Task<DetectionResult> DetectAbyssResultRetryAsync(Bitmap frame, CancellationToken ct)
    {
        if (!IsAbyss) return DetectionResult.NotFound;
        if (frame.Width != 800 || frame.Height != 1000)
            return DetectionResult.NotFound;

        // A confirmed clear animation must never be accepted as the result row.
        if ((await DetectAbyssClearPromptAsync(frame, ct)).Found)
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
    }

    private async Task RetryAbyssResultAsync(CancellationToken ct)
    {
        if (!IsAbyss) throw new InvalidOperationException("어비스 결과 전용 처리입니다.");
        var timer = Stopwatch.StartNew();
        DetectionResult previous = DetectionResult.NotFound;
        DetectionResult previousClear = DetectionResult.NotFound;
        int clearRecoveries = 0;
        while (timer.Elapsed < TimeSpan.FromSeconds(120))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var clear = await DetectAbyssClearPromptAsync(frame, ct);
            if (clear.Found)
            {
                previous = DetectionResult.NotFound;
                if (previousClear.Found && clear.Bounds.IntersectsWith(previousClear.Bounds))
                {
                    if (clearRecoveries >= 2)
                        throw new InvalidOperationException("어비스 결과 대기 중 클리어 연출이 반복되어 정지합니다.");
                    ct.ThrowIfCancellationRequested();
                    Log?.Invoke("[어비스] 결과 대기 중 클리어 연출 2회 확인 -> 터치 후 실제 결과 화면 대기");
                    await AdvanceAbyssClearScreenAsync(clear, ct);
                    clearRecoveries++;
                    previousClear = DetectionResult.NotFound;
                    continue;
                }
                previousClear = clear;
                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                continue;
            }
            previousClear = DetectionResult.NotFound;
            var retry = await DetectAbyssResultRetryAsync(frame, ct);
            if (retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds))
            {
                ct.ThrowIfCancellationRequested();
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");
                _input.ClickClientPoint(_hwnd, retry.Center);
                await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                await WaitForAbyssRetryTransitionAsync(ct);
                return;
            }
            previous = retry;
            // No monitors, alternate clicks or entry recovery while awaiting results.
            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }
        throw new InvalidOperationException("어비스 결과의 아래 중앙 다시 하기를 확인하지 못해 정지합니다. 나가기/다른 던전 가기로 우회하지 않습니다.");
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
            var retry = await DetectAbyssResultRetryAsync(frame, ct);
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
