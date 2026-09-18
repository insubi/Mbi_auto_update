using System.Diagnostics;

namespace DungeonVisionBot;

internal sealed class RestartCycleException : Exception { }

internal sealed class ScenarioEngine : IDisposable
{
    private nint _hwnd;
    private readonly AppSettings _settings;
    private readonly ScenarioDefinition _scenario;
    private readonly TargetDetector _detector;
    private readonly WindowCapture _capture = new();
    private readonly IInputController _input;
    private readonly string _baseDir;
    private readonly string? _preRoute;
    private readonly Dictionary<string, long> _monitorLastAction = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, long> _monitorLastScan = new(StringComparer.OrdinalIgnoreCase);
    private int _cycle;
    private long _lastAbyssOutsideHudScoreLog;
    private int _currentStepIndex;
    private int _resumeStepIndex;

    public event Action<string>? Log;
    public string InputMode => _input.ModeName;

    public ScenarioEngine(nint hwnd, AppSettings settings, ScenarioDefinition scenario, List<TargetDefinition> targets, string baseDir, string? preRoute = null)
    {
        _hwnd = hwnd;
        _settings = settings;
        _scenario = scenario;
        _baseDir = baseDir;
        _preRoute = preRoute;
        _detector = new TargetDetector(targets, baseDir);
        _input = CreateInput(settings);
    }

    private IInputController CreateInput(AppSettings s)
    {
        if (!s.UseInterception)
        {
            throw new InvalidOperationException(
                "UseInterception=false 입니다. 마비노기 모바일 클릭은 Interception만 사용하도록 설정하세요.");
        }

        try
        {
            return new InterceptionInput(
                s.InterceptionMouseDevice,
                s.InterceptionKeyboardDevice);
        }
        catch (DllNotFoundException ex)
        {
            throw new InvalidOperationException(
                "interception.dll을 찾지 못했습니다. " +
                "interception.dll(x64)을 DungeonVisionBot.exe 옆에 두세요.",
                ex);
        }
        catch (BadImageFormatException ex)
        {
            throw new InvalidOperationException(
                "interception.dll 비트수가 맞지 않습니다. x64 DLL을 사용하세요.",
                ex);
        }
    }

    public async Task RunAsync(CancellationToken ct)
    {
        Log?.Invoke($"입력 모드: {InputMode}");
        if (!string.IsNullOrWhiteSpace(_preRoute))
            await RunDungeonPreRouteAsync(_preRoute!, ct);

        int recoveryFailures = 0;
        int repeatedRecoveryStep = -1;
        int repeatedRecoveryCount = 0;

        do
        {
            int maxStep = Math.Max(0, _scenario.Steps.Count - 1);
            int startStep = Math.Clamp(_resumeStepIndex, 0, maxStep);
            bool resuming = _resumeStepIndex > 0;
            _resumeStepIndex = 0;

            _cycle++;
            if (resuming)
                Log?.Invoke($"===== {_cycle}판 자동복구 재개: {startStep + 1}. {_scenario.Steps[startStep].Name} =====");
            else
                Log?.Invoke($"===== {_cycle}판 시작 =====");

            try
            {
                for (int i = startStep; i < _scenario.Steps.Count; i++)
                {
                    _currentStepIndex = i;
                    ct.ThrowIfCancellationRequested();
                    await ExecuteStepAsync(_scenario.Steps[i], ct);
                }

                recoveryFailures = 0;
                repeatedRecoveryStep = -1;
                repeatedRecoveryCount = 0;
                _resumeStepIndex = 0;
                Log?.Invoke($"===== {_cycle}판 완료 =====");
            }
            catch (RestartCycleException)
            {
                recoveryFailures = 0;
                repeatedRecoveryStep = -1;
                repeatedRecoveryCount = 0;
                _resumeStepIndex = 0;
                Log?.Invoke("감시 항목에 의해 현재 판을 처음부터 다시 시작합니다.");
            }
            catch (TimeoutException ex) when (_settings.AutoRecoveryEnabled)
            {
                int max = Math.Max(1, _settings.AutoRecoveryMaxAttempts);
                bool recovered = false;

                while (!recovered)
                {
                    recoveryFailures++;
                    Log?.Invoke($"[자동복구] {recoveryFailures}/{max} 단계 시간초과: {ex.Message}");
                    await SaveRecoveryScreenshotAsync($"recovery_{recoveryFailures}", ct);

                    recovered = await TrySmartRecoveryAsync(ct);
                    if (recovered)
                    {
                        bool abyss = string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);
                        if (abyss)
                        {
                            _resumeStepIndex = 0;
                            Log?.Invoke($"[자동복구] {recoveryFailures}/{max} 어비스 복귀 확인 -> 처음부터 재시작");
                        }
                        else
                        {
                            int s = Math.Clamp(_resumeStepIndex, 0, maxStep);
                            if (repeatedRecoveryStep == s)
                                repeatedRecoveryCount++;
                            else
                            {
                                repeatedRecoveryStep = s;
                                repeatedRecoveryCount = 1;
                            }

                            Log?.Invoke($"[던전 자동복구] 현재 화면 확인 완료 -> {s + 1}. {_scenario.Steps[s].Name} 단계에서 재시작 (동일 단계 복구 {repeatedRecoveryCount}/{max})");
                            if (repeatedRecoveryCount >= max)
                            {
                                Log?.Invoke($"[던전 자동복구] 같은 복구 단계가 {max}회 반복됨 -> 무한 반복 방지를 위해 안전 정지");
                                throw new TimeoutException($"같은 복구 단계 '{_scenario.Steps[s].Name}'가 {max}회 반복되어 안전 정지합니다. 마지막 오류: {ex.Message}", ex);
                            }
                        }

                        recoveryFailures = 0;
                        break;
                    }

                    Log?.Invoke($"[던전 자동복구] {recoveryFailures}/{max} ESC 후 알고 있는 단계 화면 미확인");
                    if (recoveryFailures >= max)
                    {
                        Log?.Invoke($"[자동복구] {max}/{max} 실패 -> 안전 정지");
                        throw new TimeoutException($"Smart Recovery가 {max}회 실패했습니다. 마지막 오류: {ex.Message}", ex);
                    }

                    await Task.Delay(TimeSpan.FromSeconds(Math.Max(1, _settings.AutoRecoveryDelaySeconds)), ct);
                }

                await Task.Delay(TimeSpan.FromSeconds(Math.Max(1, _settings.AutoRecoveryDelaySeconds)), ct);
            }
        } while (_scenario.Repeat && !ct.IsCancellationRequested);
    }

    // DUNGEON_WORLD_ROUTE_V11
    private async Task RunDungeonPreRouteAsync(string route, CancellationToken ct)
    {
        bool isPeaca = route.StartsWith("peaca_", StringComparison.OrdinalIgnoreCase);
        bool isRunda = route.StartsWith("runda_", StringComparison.OrdinalIgnoreCase);
        bool isFiod = route.StartsWith("fiod_", StringComparison.OrdinalIgnoreCase);
        bool d11 = route.EndsWith("d1_1", StringComparison.OrdinalIgnoreCase);
        bool d21 = route.EndsWith("d2_1", StringComparison.OrdinalIgnoreCase);
        if ((!isPeaca && !isRunda && !isFiod) || (!d11 && !d21))
            throw new InvalidOperationException($"지원하지 않는 던전 자동 이동 경로: {route}");

        string dungeonName = isPeaca ? "페카 고분" : isRunda ? "룬다 던전" : "피오드 던전";
        string destination = isPeaca
            ? (d11 ? "페카 심층 1-1" : "페카 심층 2-1")
            : $"{dungeonName.Replace(" 던전", "")} {(d11 ? "1-1" : "2-1")}";
        string mapTarget = isPeaca ? "route_peaca_map" : isRunda ? "route_runda_map" : "route_fiod_map";
        string popupTarget = isPeaca ? "route_peaca_popup_title" : isRunda ? "route_runda_popup_title" : "route_fiod_popup_title";
        string arrivalTarget = isPeaca ? "route_peaca_title" : isRunda ? "route_runda_title" : "route_fiod_title";

        Log?.Invoke($"[던전 자동이동] 시작 -> {destination}");
        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);

        using var beforeMapOpen = await CaptureGameWindowAsync(ct);
        Log?.Invoke("[던전 자동이동] M 입력 -> 지도 열기");
        _input.TapScanCode(0x32); // M
        await Task.Delay(1200, ct);

        using var localMapFrame = await CaptureGameWindowAsync(ct);
        double mapOpenDiff = MapFrameDifference(beforeMapOpen, localMapFrame);
        Log?.Invoke($"[던전 자동이동] M 입력 후 화면변화={mapOpenDiff:0.00}");
        if (mapOpenDiff <= 6.0)
            throw new TimeoutException("M 입력 후 지도 화면 전환을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        var ullaBreadcrumbPoint = new Point(82, 66);
        Log?.Invoke($"[던전 자동이동] 좌측 상단 울라 대륙 고정 위치 클릭 @ {ullaBreadcrumbPoint}");
        _input.ClickClientPoint(_hwnd, ullaBreadcrumbPoint);
        await Task.Delay(1200, ct);

        using var worldMapFrame = await CaptureGameWindowAsync(ct);
        double continentOpenDiff = MapFrameDifference(localMapFrame, worldMapFrame);
        Log?.Invoke($"[던전 자동이동] 울라 대륙 클릭 후 화면변화={continentOpenDiff:0.00}");
        if (continentOpenDiff <= 6.0)
            throw new TimeoutException("좌측 상단 울라 대륙 고정 위치 클릭 후 월드맵 전환을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        await AlignWorldMapTopLeftAsync(ct);
        var mapLabel = await FindDungeonOnWorldMapAsync(mapTarget, dungeonName, ct);
        if (!mapLabel.Found)
            throw new TimeoutException($"울라 대륙 지도를 제한 범위까지 탐색했지만 '{dungeonName}'을 찾지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        // The OCR label is ONLY an anchor. Never click the text itself.
        // Find the saturated purple/blue-highlight dungeon icon immediately above that label.
        using var iconFrame = await CaptureGameWindowAsync(ct);
        if (!TryFindDungeonIconAboveLabel(iconFrame, mapLabel.Bounds, out var iconBounds))
            throw new TimeoutException($"{dungeonName} 글씨는 찾았지만 위쪽 던전 아이콘을 확인하지 못했습니다. 글씨나 대체 좌표를 누르지 않고 정지합니다.");

        var iconCenter = new Point(iconBounds.Left + iconBounds.Width / 2, iconBounds.Top + iconBounds.Height / 2);
        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[던전 자동이동] {dungeonName} OCR 확인 -> 위 던전 아이콘 클릭 @ {iconBounds}");
        _input.ClickClientPoint(_hwnd, iconCenter);
        await Task.Delay(700, ct);

        bool popupReady = await WaitForTargetPairAsync(popupTarget, "route_go_here", 8, ct);
        if (!popupReady)
            throw new TimeoutException($"{dungeonName} 아이콘 클릭 후 '{dungeonName} + 여기로 가기' 확인에 실패했습니다. Space를 누르지 않습니다.");

        Log?.Invoke($"[던전 자동이동] {dungeonName} + 여기로 가기 확인 -> Space");
        _input.TapScanCode(0x39);
        await Task.Delay(800, ct);

        if (isPeaca)
        {
            bool arrived = await WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 300, ct);
            if (!arrived)
                throw new TimeoutException("이동 후 5분 안에 페카 고분 도착/심층 던전 탭을 확인하지 못했습니다.");

            DetectionResult deepTab;
            using (var arrivedFrame = await CaptureGameWindowAsync(ct))
                deepTab = await _detector.DetectAsync("route_deep_tab", arrivedFrame, ct);
            if (!deepTab.Found)
                throw new TimeoutException("페카 고분 도착 후 심층 던전 탭을 다시 확인하지 못했습니다.");

            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            Log?.Invoke($"[던전 자동이동] 심층 던전 탭 클릭 @ {deepTab.Bounds}");
            _input.ClickClientPoint(_hwnd, deepTab.Center);
            await Task.Delay(900, ct);
        }
        else
        {
            var arrived = await WaitForTargetAsync(arrivalTarget, 300, ct);
            if (!arrived.Found)
                throw new TimeoutException($"이동 후 5분 안에 {dungeonName} 도착 화면을 확인하지 못했습니다.");
            Log?.Invoke($"[던전 자동이동] {dungeonName} 도착 화면 확인");
        }

        string slotTarget = isPeaca
            ? (d11 ? "route_d1_1" : "route_d2_1")
            : (d11 ? "route_regular_1_1" : "route_regular_2_1");
        string enterTarget = isPeaca
            ? (d11 ? "route_enter_d1_1" : "route_enter_d2_1")
            : (d11 ? "route_enter_regular_1_1" : "route_enter_regular_2_1");

        var slot = await WaitForDungeonSlotAsync(slotTarget, 30, ct);
        if (!slot.Found)
            throw new TimeoutException($"{destination}의 {(d11 ? "1-1" : "2-1")} 표기를 30초 안에 찾지 못했습니다. best={slot.Score:0.000}, bounds={slot.Bounds}. 다른 구역을 대신 누르지 않습니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        Log?.Invoke($"[던전 자동이동] {destination} 구역 확인 -> 클릭 @ {slot.Bounds}");
        _input.ClickClientPoint(_hwnd, slot.Center);
        await Task.Delay(650, ct);

        var enter = await WaitForTargetAsync(enterTarget, 8, ct);
        if (!enter.Found)
            throw new TimeoutException($"{destination} 선택 후 정확한 진입 문구를 확인하지 못했습니다. Space를 누르지 않습니다.");

        Log?.Invoke($"[던전 자동이동] {destination} 진입 문구 확인 -> Space");
        _input.TapScanCode(0x39);

        var handoff = await WaitForTargetAsync("enter_bottom", 20, ct);
        if (!handoff.Found)
            throw new TimeoutException($"{destination} 진입 후 기존 던전 매크로 초입 '입장하기' 화면을 20초 안에 확인하지 못했습니다.");

        Log?.Invoke("[던전 자동이동] 기존 던전 매크로 초입 확인 완료 -> 기존 선택됨/도전/입장 로직으로 인계");
    }

    private async Task<DetectionResult> WaitForDungeonSlotAsync(string targetId, int timeoutSeconds, CancellationToken ct)
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

    private async Task<DetectionResult> WaitForTargetAsync(string targetId, int timeoutSeconds, CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        while (sw.Elapsed < TimeSpan.FromSeconds(timeoutSeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var r = await _detector.DetectAsync(targetId, frame, ct);
            if (r.Found) return r;
            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }
        return DetectionResult.NotFound;
    }

    private async Task<bool> WaitForTargetPairAsync(string firstId, string secondId, int timeoutSeconds, CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        while (sw.Elapsed < TimeSpan.FromSeconds(timeoutSeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var first = await _detector.DetectAsync(firstId, frame, ct);
            var second = await _detector.DetectAsync(secondId, frame, ct);
            if (first.Found && second.Found)
            {
                Log?.Invoke($"[던전 자동이동] 동시 확인: {firstId} + {secondId}");
                return true;
            }
            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);
        }
        return false;
    }

    private async Task AlignWorldMapTopLeftAsync(CancellationToken ct)
    {
        const double StableThreshold = 6.0;
        int stable = 0;
        Log?.Invoke("[던전 자동이동] 울라 월드맵 좌상단 끝 정렬 시작");

        for (int attempt = 1; attempt <= 12; attempt++)
        {
            ct.ThrowIfCancellationRequested();
            using var before = await CaptureGameWindowAsync(ct);
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            _input.DragClientPoint(_hwnd, new Point(270, 330), new Point(520, 620), 800);
            await Task.Delay(650, ct);
            using var after = await CaptureGameWindowAsync(ct);
            double diff = MapFrameDifference(before, after);
            stable = diff <= StableThreshold ? stable + 1 : 0;
            Log?.Invoke($"[던전 자동이동] 좌상단 정렬 {attempt}/12 · 화면변화={diff:0.00} · 끝판정={stable}/2");
            if (stable >= 2)
            {
                Log?.Invoke("[던전 자동이동] 화면 변화 거의 없음 2회 연속 -> 좌상단 끝 도달 확정");
                return;
            }
        }

        throw new TimeoutException("월드맵을 좌상단 끝으로 정렬하지 못했습니다. 12회 제한 후 정지합니다.");
    }

    private async Task<DetectionResult> FindDungeonOnWorldMapAsync(
        string mapTarget,
        string dungeonName,
        CancellationToken ct)
    {
        const double EdgeThreshold = 6.0;
        bool moveViewportRight = true;
        Log?.Invoke($"[던전 자동이동] {dungeonName} · 좌상단 기준 지그재그 탐색 시작");

        for (int row = 0; row < 4; row++)
        {
            int edgeStable = 0;
            for (int col = 0; col < 6; col++)
            {
                ct.ThrowIfCancellationRequested();
                using var frame = await CaptureGameWindowAsync(ct);
                var found = await _detector.DetectAsync(mapTarget, frame, ct);
                if (found.Found)
                {
                    Log?.Invoke($"[던전 자동이동] {dungeonName} 글씨 발견 row={row + 1}, col={col + 1} @ {found.Bounds}");
                    return found;
                }

                if (col == 5) break;
                var from = moveViewportRight ? new Point(530, 440) : new Point(220, 440);
                var to = moveViewportRight ? new Point(220, 440) : new Point(530, 440);
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                _input.DragClientPoint(_hwnd, from, to, 850);
                await Task.Delay(600, ct);
                using var after = await CaptureGameWindowAsync(ct);
                double diff = MapFrameDifference(frame, after);
                edgeStable = diff <= EdgeThreshold ? edgeStable + 1 : 0;
                Log?.Invoke($"[던전 자동이동] 가로 탐색 row={row + 1}, step={col + 1} · 화면변화={diff:0.00} · 경계={edgeStable}/2");
                if (edgeStable >= 2) break;
            }

            using (var last = await CaptureGameWindowAsync(ct))
            {
                var found = await _detector.DetectAsync(mapTarget, last, ct);
                if (found.Found) return found;
            }
            if (row == 3) break;

            using var beforeDown = await CaptureGameWindowAsync(ct);
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            _input.DragClientPoint(_hwnd, new Point(380, 650), new Point(380, 320), 850);
            await Task.Delay(650, ct);
            using var afterDown = await CaptureGameWindowAsync(ct);
            double downDiff = MapFrameDifference(beforeDown, afterDown);
            Log?.Invoke($"[던전 자동이동] 다음 줄 이동 {row + 1}-> {row + 2} · 화면변화={downDiff:0.00}");
            if (downDiff <= EdgeThreshold)
            {
                using var confirmBefore = await CaptureGameWindowAsync(ct);
                _input.DragClientPoint(_hwnd, new Point(380, 650), new Point(380, 320), 850);
                await Task.Delay(650, ct);
                using var confirmAfter = await CaptureGameWindowAsync(ct);
                double confirmDiff = MapFrameDifference(confirmBefore, confirmAfter);
                Log?.Invoke($"[던전 자동이동] 세로 경계 재확인 · 화면변화={confirmDiff:0.00}");
                if (confirmDiff <= EdgeThreshold) break;
            }
            moveViewportRight = !moveViewportRight;
        }

        return DetectionResult.NotFound;
    }

    // The map label is an OCR anchor only. This validates the colored dungeon icon above it.
    // Purple is the normal state; the selected/highlight state can render blue, so both are accepted.
    private static bool TryFindDungeonIconAboveLabel(Bitmap frame, Rectangle labelBounds, out Rectangle iconBounds)
    {
        iconBounds = Rectangle.Empty;
        if (labelBounds.Width <= 0 || labelBounds.Height <= 0) return false;

        int centerX = labelBounds.Left + labelBounds.Width / 2;
        int searchWidth = Math.Max(120, labelBounds.Width + 100);
        var search = WindowCapture.ClampRoi(
            new Rectangle(centerX - searchWidth / 2, labelBounds.Top - 105, searchWidth, 105),
            frame.Size);
        if (search.Width < 20 || search.Height < 20) return false;

        int minX = int.MaxValue, minY = int.MaxValue;
        int maxX = int.MinValue, maxY = int.MinValue;
        int pixels = 0;

        for (int y = search.Top; y < search.Bottom; y++)
        {
            for (int x = search.Left; x < search.Right; x++)
            {
                Color c = frame.GetPixel(x, y);
                bool purpleOrBlue =
                    c.B >= 140 &&
                    c.B > c.G * 1.12 &&
                    c.G < 190 &&
                    (c.R >= 65 || c.B >= 210);

                if (!purpleOrBlue) continue;
                pixels++;
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
        }

        if (pixels < 120 || minX == int.MaxValue) return false;

        var bounds = Rectangle.FromLTRB(minX, minY, maxX + 1, maxY + 1);
        if (bounds.Width < 18 || bounds.Height < 18 || bounds.Width > 85 || bounds.Height > 85)
            return false;

        // The icon must actually be above the OCR text, not beside/below it.
        if (bounds.Bottom > labelBounds.Top + 4)
            return false;

        iconBounds = bounds;
        return true;
    }

    private static double MapFrameDifference(Bitmap before, Bitmap after)
    {
        int width = Math.Min(before.Width, after.Width);
        int height = Math.Min(before.Height, after.Height);
        var roi = WindowCapture.ClampRoi(new Rectangle(70, 140, 490, 560), new Size(width, height));
        if (roi.Width < 20 || roi.Height < 20) return double.MaxValue;

        long sum = 0;
        long samples = 0;
        for (int y = roi.Top; y < roi.Bottom; y += 12)
        {
            for (int x = roi.Left; x < roi.Right; x += 12)
            {
                Color a = before.GetPixel(x, y);
                Color b = after.GetPixel(x, y);
                sum += Math.Abs(a.R - b.R) + Math.Abs(a.G - b.G) + Math.Abs(a.B - b.B);
                samples++;
            }
        }
        return samples == 0 ? double.MaxValue : sum / (samples * 3.0);
    }

    private int FindDungeonStepIndex(string targetId)
    {
        for (int i = 0; i < _scenario.Steps.Count; i++)
        {
            if (_scenario.Steps[i].Target.Equals(targetId, StringComparison.OrdinalIgnoreCase))
                return i;
        }
        return 0;
    }

    private async Task<int?> DetectKnownDungeonRecoveryStepAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();

        while (sw.Elapsed < TimeSpan.FromSeconds(8))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(frame, ct))
            {
                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                continue;
            }

            // Most specific later-stage screens first.
            var retry = await _detector.DetectAsync("retry", frame, ct);
            if (retry.Found)
            {
                int step = FindDungeonStepIndex("retry");
                Log?.Invoke($"[던전 자동복구] 다시 하기 확인 -> {step + 1}단계 재개");
                return step;
            }

            var touch = await _detector.DetectAsync("touch_result", frame, ct);
            if (touch.Found)
            {
                int step = FindDungeonStepIndex("touch_result");
                Log?.Invoke($"[던전 자동복구] 전투 종료/터치 화면 확인 -> {step + 1}단계 재개");
                return step;
            }

            // selected/challenge are the same logical entry-state stage.
            var selected = await _detector.DetectAsync("selected", frame, ct);
            if (selected.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] 선택됨 확인 -> 도전 상태 확인 {step + 1}단계 재개");
                return step;
            }

            var challenge = await _detector.DetectAsync("challenge", frame, ct);
            if (challenge.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] 도전 확인 -> {step + 1}단계 재개");
                return step;
            }

            // Entry text alone never authorizes entry; return through challenge verification.
            var enter = await _detector.DetectAsync("enter_bottom", frame, ct);
            if (enter.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] 입장하기 확인 -> 안전하게 도전 상태 확인 {step + 1}단계 재개");
                return step;
            }

            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);
        }

        return null;
    }

    // DUNGEON_SCREEN_FIRST_RECOVERY_V6
    // Recovery rule: classify the CURRENT screen first. Only if no known state is found
    // is one ESC sent as a last resort, followed by one more classification pass.
    private async Task<bool> TrySmartRecoveryAsync(CancellationToken ct)
    {
        bool abyss = string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);
        if (abyss)
            return await TryAbyssInternalRecoveryAsync(ct);

        try
        {
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            NativeMethods.SetForegroundWindow(_hwnd);

            Log?.Invoke($"[던전 자동복구] {_currentStepIndex + 1}단계 오류 -> ESC 없이 현재 화면 먼저 판별");
            int? resumeStep = await DetectKnownDungeonRecoveryStepAsync(ct);
            if (resumeStep.HasValue)
            {
                _resumeStepIndex = resumeStep.Value;
                Log?.Invoke($"[던전 자동복구] 현재 화면에서 알려진 단계 확인 -> ESC 없이 {_resumeStepIndex + 1}단계 재개");
                return true;
            }

            // Unknown screen only: one ESC is the last resort for this recovery attempt.
            Log?.Invoke("[던전 자동복구] 현재 화면 8초간 미확인 -> 최후 수단 ESC 1회 입력 후 재판별");
            _input.TapScanCode(0x01);
            await Task.Delay(800, ct);

            resumeStep = await DetectKnownDungeonRecoveryStepAsync(ct);
            if (resumeStep.HasValue)
            {
                _resumeStepIndex = resumeStep.Value;
                Log?.Invoke($"[던전 자동복구] ESC 후 알려진 단계 확인 -> {_resumeStepIndex + 1}단계 재개");
                return true;
            }

            Log?.Invoke("[던전 자동복구] ESC 후에도 알려진 단계 미확인 -> 이번 복구 시도 실패 (추가 ESC 없음)");
            return false;
        }
        catch (Exception ex)
        {
            Log?.Invoke($"[던전 자동복구] 화면 우선 판별 예외: {ex.Message}");
            return false;
        }
    }

    private async Task<bool> TryAbyssInternalRecoveryAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        const int RecoveryTimeoutSeconds = 660;
        long lastTouchClick = 0;
        long lastExitClick = 0;
        long lastPopupClick = 0;
        int touchClicks = 0;
        int exitClicks = 0;
        bool treasureSeen = false;
        bool clearScreenSeen = false;
        bool clearTransitionConfirmed = false;
        int clearGoneConsecutive = 0;
        int outsideConsecutive = 0;

        Log?.Invoke("[어비스 자동복구] 상태 기반 복구 시작: 전투 대기 -> 클리어 터치 -> 보물상자 확인 -> 나가기 -> 던전 밖 HUD 확인");

        while (sw.Elapsed < TimeSpan.FromSeconds(RecoveryTimeoutSeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            long now = Environment.TickCount64;

            if (await DetectAbyssOutsideWorkflowAsync(frame, ct))
            {
                Log?.Invoke("[어비스 자동복구] 던전 밖 HUD 3/4 이상 확인 -> 복구 즉시 완료, 처음부터 재시작");
                return true;
            }
            outsideConsecutive = 0;

            if (now - lastPopupClick >= 2500)
            {
                var popupClose = await _detector.DetectAsync("abyss_popup_close", frame, ct);
                if (popupClose.Found)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[어비스 자동복구] 팝업 닫기 이미지 확인 -> 클릭 @ {popupClose.Bounds}");
                    _input.ClickClientPoint(_hwnd, popupClose.Center);
                    lastPopupClick = now;
                    await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                    continue;
                }
            }

            var clearVisual = await DetectAbyssConfirmedClearAsync(frame, ct);
            if (clearVisual.Found)
            {
                clearScreenSeen = true;
                clearTransitionConfirmed = false;
                clearGoneConsecutive = 0;
                var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
                if (touch.Found && now - lastTouchClick >= 1800)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    touchClicks++;
                    Log?.Invoke($"[어비스 자동복구] 클리어 화면 동시 이미지 확인 완료 -> 화면 터치 {touchClicks}회 @ {touch.Bounds}");
                    _input.ClickClientPoint(_hwnd, touch.Center);
                    lastTouchClick = now;
                    await Task.Delay(Math.Max(900, _settings.ClickSettleMs), ct);
                    continue;
                }
                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                continue;
            }

            if (clearScreenSeen && !clearTransitionConfirmed)
            {
                var residual = await DetectAbyssClearVisualAsync(frame, ct);
                if (!residual.Found)
                {
                    clearGoneConsecutive++;
                    Log?.Invoke($"[어비스 자동복구] 클리어 화면 사라짐 확인 {clearGoneConsecutive}/3");
                    if (clearGoneConsecutive >= 3)
                    {
                        clearTransitionConfirmed = true;
                        Log?.Invoke("[어비스 자동복구] 클리어 화면 3회 연속 사라짐 확인 -> 보물상자/나가기 탐색");
                    }
                }
                else
                {
                    clearGoneConsecutive = 0;
                }
                if (!clearTransitionConfirmed)
                {
                    await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                    continue;
                }
            }

            if (!treasureSeen)
            {
                var treasure = await _detector.DetectAsync("abyss_treasure_chest", frame, ct);
                if (treasure.Found)
                {
                    treasureSeen = true;
                    Log?.Invoke($"[어비스 자동복구] 보물상자 확인 완료 @ {treasure.Bounds} -> 나가기 탐색");
                }
            }

            if (now - lastExitClick >= 2200)
            {
                var exit = await _detector.DetectAsync("abyss_exit", frame, ct);
                if (exit.Found)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    exitClicks++;
                    Log?.Invoke($"[어비스 자동복구] 나가기 확인 {exitClicks}회 -> 클릭 @ {exit.Bounds}");
                    _input.ClickClientPoint(_hwnd, exit.Center);
                    lastExitClick = now;
                    await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);
                    continue;
                }
            }

            // No recovery UI found: this can simply be active combat. Do not press ESC.
            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);
        }

        Log?.Invoke($"[어비스 자동복구] {RecoveryTimeoutSeconds}초 동안 던전 밖 복귀를 완료하지 못함");
        return false;
    }

    private const int MaxDebugFiles = 200;
    private const long MaxDebugBytes = 268435456;

    private void PruneDebugScreenshots()
    {
        try
        {
            string dir = Path.Combine(_baseDir, "debug");
            if (!Directory.Exists(dir)) return;
            var files = new DirectoryInfo(dir).GetFiles("*.png")
                .OrderByDescending(f => f.LastWriteTimeUtc).ToList();
            long total = 0;
            for (int i = 0; i < files.Count; i++)
            {
                FileInfo f = files[i];
                if (i >= MaxDebugFiles || total + f.Length > MaxDebugBytes)
                {
                    try { f.Delete(); } catch { }
                }
                else total += f.Length;
            }
        }
        catch { }
    }

    private async Task SaveRecoveryScreenshotAsync(string label, CancellationToken ct)
    {
        if (!_settings.SaveScreenshotOnTimeout) return;
        try
        {
            Directory.CreateDirectory(Path.Combine(_baseDir, "debug"));
            using var shot = await CaptureGameWindowAsync(ct);
            string path = Path.Combine(_baseDir, "debug", $"{label}_{DateTime.Now:yyyyMMdd_HHmmss}.png");
            shot.Save(path);
            PruneDebugScreenshots();
            Log?.Invoke($"[자동복구] 디버그 캡처 저장: {path}");
        }
        catch { }
    }

    // DUNGEON_CHALLENGE_DISAMBIGUATION_V5
    // Entry rule: selected -> click once -> challenge confirmed -> enter.
    // Never click when selected/challenge visual evidence is ambiguous.
    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)
    {
        const int RequiredConsecutive = 3;
        const int ConfirmIntervalMs = 300;
        const int FinalDelayMs = 800;
        const int MaxVerifySeconds = 45;
        const double VisualLeadMargin = 0.07;

        int challengeConsecutive = 0;
        long lastSelectedClick = 0;
        long lastAmbiguousLog = 0;
        int normalResultRetryClicks = 0;
        var timer = Stopwatch.StartNew();

        Log?.Invoke("[도전 안전확인] 선택됨/도전 분리 판정 시작");

        async Task<(int State, Point ClickPoint, double SelectedScore, double ChallengeScore)> ClassifyAsync(Bitmap frame)
        {
            // Exact/near-exact text gets priority over visual similarity.
            var challengeText = await _detector.DetectAsync("challenge_confirm_strict", frame, ct);
            if (challengeText.Found)
                return (2, Point.Empty, 0.0, 1.0);

            var selectedText = await _detector.DetectAsync("selected_ocr_strict", frame, ct);
            if (selectedText.Found)
                return (1, selectedText.Center, 1.0, 0.0);

            // OCR failed: compare the two button images against each other.
            // A single loose template match is not enough to click anything.
            var selectedVisual = await _detector.DetectAsync("selected_red_visual", frame, ct);
            var challengeVisual = await _detector.DetectAsync("challenge_visual", frame, ct);

            double s = selectedVisual.Score;
            double c = challengeVisual.Score;

            if (selectedVisual.Found && challengeVisual.Found)
            {
                if (s >= c + VisualLeadMargin)
                    return (1, selectedVisual.Center, s, c);
                if (c >= s + VisualLeadMargin)
                    return (2, Point.Empty, s, c);
                return (0, Point.Empty, s, c);
            }

            if (selectedVisual.Found && !challengeVisual.Found)
                return (1, selectedVisual.Center, s, c);
            if (challengeVisual.Found && !selectedVisual.Found)
                return (2, Point.Empty, s, c);

            return (0, Point.Empty, s, c);
        }

        while (timer.Elapsed < TimeSpan.FromSeconds(MaxVerifySeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            // DUNGEON_RESULT_RETRY_FASTPATH_V8
            // A normal dungeon clear can leave us on the reward/result screen while this
            // verifier is waiting for selected -> challenge -> enter. Handle the existing
            // hybrid "retry" target here before the 45-second timeout so a normal clear does
            // not become a generic auto-recovery alert. Never use a fallback coordinate.
            var normalRetry = await _detector.DetectAsync("retry", frame, ct);
            if (normalRetry.Found)
            {
                challengeConsecutive = 0;
                Log?.Invoke($"[던전 결과] 다시 하기 감지 1/2 score={normalRetry.Score:0.000}");
                await Task.Delay(220, ct);

                using var retryConfirmFrame = await CaptureGameWindowAsync(ct);
                var retryConfirm = await _detector.DetectAsync("retry", retryConfirmFrame, ct);
                if (retryConfirm.Found)
                {
                    Log?.Invoke($"[던전 결과] 다시 하기 2/2 연속 확인 score={retryConfirm.Score:0.000}");

                    if (normalResultRetryClicks >= 2)
                    {
                        Log?.Invoke("[던전 결과] 정상 다시 하기 클릭 2회 소진 -> 기존 45초 타임아웃/자동복구에 맡김");
                        await Task.Delay(ConfirmIntervalMs, ct);
                        continue;
                    }

                    normalResultRetryClicks++;
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[던전 결과] 정상 다시 하기 클릭 {normalResultRetryClicks}/2 @ {retryConfirm.Center}");
                    _input.ClickClientPoint(_hwnd, retryConfirm.Center);
                    await Task.Delay(Math.Max(900, _settings.ClickSettleMs), ct);

                    using var afterRetryFrame = await CaptureGameWindowAsync(ct);
                    var stillRetry = await _detector.DetectAsync("retry", afterRetryFrame, ct);
                    if (!stillRetry.Found)
                    {
                        timer.Restart();
                        lastSelectedClick = 0;
                        Log?.Invoke("[던전 결과] 다시 하기 화면 이탈 확인 -> 정상 진행, 45초 검증 타이머 재시작");
                    }
                    else
                    {
                        Log?.Invoke("[던전 결과] 다시 하기 클릭 후 화면 유지 -> 재확인 (임의 좌표 클릭 없음)");
                    }

                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                Log?.Invoke("[던전 결과] 다시 하기 2/2 확인 실패 -> 클릭 안 함");
            }

            if (await CheckMonitorsAsync(frame, ct))
            {
                challengeConsecutive = 0;
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            var state = await ClassifyAsync(frame);

            if (state.State == 1) // selected
            {
                challengeConsecutive = 0;
                long now = Environment.TickCount64;
                if (now - lastSelectedClick >= 1200)
                {
                    Log?.Invoke($"[도전 안전확인] 선택됨 확정 S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000} -> 1회 클릭");
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _input.ClickClientPoint(_hwnd, state.ClickPoint);
                    lastSelectedClick = now;
                    await Task.Delay(Math.Max(650, _settings.ClickSettleMs), ct);
                }
                else
                {
                    await Task.Delay(ConfirmIntervalMs, ct);
                }
                continue;
            }

            if (state.State == 0) // ambiguous / unknown
            {
                challengeConsecutive = 0;
                long now = Environment.TickCount64;
                if (now - lastAmbiguousLog >= 1500)
                {
                    Log?.Invoke($"[도전 안전확인] 판정 보류 S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000} -> 클릭 안 함");
                    lastAmbiguousLog = now;
                }
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            // challenge: do NOT click the challenge/selected toggle anymore.
            challengeConsecutive++;
            Log?.Invoke($"[도전 안전확인] 도전 확정 {challengeConsecutive}/{RequiredConsecutive} S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000}");

            if (challengeConsecutive < RequiredConsecutive)
            {
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            await Task.Delay(FinalDelayMs, ct);
            using var finalFrame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(finalFrame, ct))
            {
                challengeConsecutive = 0;
                continue;
            }

            var finalState = await ClassifyAsync(finalFrame);
            var enter = await _detector.DetectAsync("enter_bottom", finalFrame, ct);

            if (finalState.State == 2 && enter.Found)
            {
                Log?.Invoke($"[도전 안전확인] 최종 도전 확인 성공 + 입장하기 확인 -> 입장 허용 (S={finalState.SelectedScore:0.000} C={finalState.ChallengeScore:0.000})");
                return;
            }

            Log?.Invoke($"[도전 안전확인] 최종 확인 보류 state={finalState.State} enter={(enter.Found ? 1 : 0)} S={finalState.SelectedScore:0.000} C={finalState.ChallengeScore:0.000}");
            challengeConsecutive = 0;
            await Task.Delay(ConfirmIntervalMs, ct);
        }

        throw new TimeoutException(
            "45초 동안 선택됨 -> 도전 -> 입장하기 상태를 안정적으로 확인하지 못했습니다.");
    }
    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int consecutive = 0;
        string[] ids =
        {
            "abyss_dungeon_hallucination_anchorage",
            "abyss_dungeon_madness_cave",
            "abyss_dungeon_scattered_waterway"
        };

        while (sw.Elapsed < TimeSpan.FromSeconds(6))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            bool foundAny = false;
            string foundId = "";

            foreach (string id in ids)
            {
                var r = await _detector.DetectAsync(id, frame, ct);
                if (!r.Found) continue;
                foundAny = true;
                foundId = id;
                break;
            }

            if (foundAny)
            {
                consecutive++;
                Log?.Invoke($"[어비스] 어비스 던전 선택 화면 확인 {consecutive}/2 ({foundId})");
                if (consecutive >= 2)
                    return true;
            }
            else
            {
                consecutive = 0;
            }

            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        return false;
    }

    private async Task ExecuteStepAsync(ScenarioStep step, CancellationToken ct)
    {
        // STABLE_CHALLENGE_GUARD_V2_CALL
        if (step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase))
        {
            await VerifyChallengeBeforeEntryAsync(ct);
        }

        Log?.Invoke($"[{step.Name}] 대기: {step.Target} / {step.TimeoutSeconds}s");
        var sw = Stopwatch.StartNew();
        bool alternativeClicked = false;
        int abyssClearConsecutive = 0;
        var abyssIconRejected = new List<Rectangle>();

        while (sw.Elapsed < TimeSpan.FromSeconds(step.TimeoutSeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            // Abyss clear screen must win over the global scene-skip monitor.
            // v67: image-only multi-scale confirmation. Rank S/OCR are not used; transition is separately verified.
            DetectionResult found;
            if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
            {
                found = await DetectAbyssConfirmedClearAsync(frame, ct);
                if (!found.Found)
                {
                    abyssClearConsecutive = 0;
                    if (await CheckMonitorsAsync(frame, ct))
                        continue;
                }
                else
                {
                    Log?.Invoke("[어비스] 클리어 화면 동시 이미지 확인 완료 -> 터치 문구 클릭 단계 진행");
                    abyssClearConsecutive = 0;
                }
            }
            else
            {
                if (await CheckMonitorsAsync(frame, ct))
                    continue;

                if (step.Target.Equals("abyss_icon", StringComparison.OrdinalIgnoreCase) && abyssIconRejected.Count > 0)
                {
                    using var masked = (Bitmap)frame.Clone();
                    using (var g = Graphics.FromImage(masked))
                    {
                        foreach (var rejected in abyssIconRejected)
                            g.FillRectangle(Brushes.Black, rejected);
                    }
                    found = await _detector.DetectAsync(step.Target, masked, ct);
                }
                else
                {
                    found = await _detector.DetectAsync(step.Target, frame, ct);
                }
            }

            if (found.Found)
            {
                Log?.Invoke($"[{step.Name}] 발견: {found.ReadText ?? found.Score.ToString("0.000")} @ {found.Bounds}");
                if (step.Type.Equals("wait_click", StringComparison.OrdinalIgnoreCase))
                {
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
                    {
                        await AdvanceAbyssClearScreenAsync(found, ct);
                    }
                    else if (step.Target.Equals("abyss_icon", StringComparison.OrdinalIgnoreCase))
                    {
                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

                        if (!await VerifyAbyssSelectionScreenAsync(ct))
                        {
                            var rejected = found.Bounds;
                            rejected.Inflate(24, 24);
                            abyssIconRejected.Add(rejected);
                            Log?.Invoke($"[어비스] 어비스 클릭 검증 실패 {abyssIconRejected.Count}/4 @ {found.Bounds} score={found.Score:0.000} -> ESC 후 해당 후보 제외");

                            _hwnd = await ResolveRequiredGameWindowAsync(ct);
                            NativeMethods.SetForegroundWindow(_hwnd);
                            _input.TapScanCode(0x01); // ESC: wrong content -> menu
                            await Task.Delay(900, ct);

                            if (abyssIconRejected.Count >= 4)
                            {
                                // Close the menu as well so Smart Recovery sees the outside HUD immediately.
                                _input.TapScanCode(0x01);
                                await Task.Delay(700, ct);
                                throw new TimeoutException("어비스 아이콘 후보 4개를 클릭 검증했지만 어비스 던전 선택 화면이 확인되지 않았습니다.");
                            }

                            continue;
                        }

                        Log?.Invoke($"[어비스] 어비스 클릭 검증 성공 @ {found.Bounds} score={found.Score:0.000}");
                    }
                    else
                    {
                        if (step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase))
                        {
                            string exactEntry = FuzzyText.Normalize(found.ReadText ?? "");
                            if (!exactEntry.Equals(FuzzyText.Normalize("입장하기"), StringComparison.OrdinalIgnoreCase))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기 정확 단어 확인 실패 -> 클릭 안 함 · OCR="{found.ReadText}" @ {found.Bounds}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            Log?.Invoke($"[던전 입장] 입장하기 단어 자체 중앙 클릭 @ {found.Bounds} center={found.Center}");
                        }

                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(_settings.ClickSettleMs, ct);
                    }

                    if (step.Target.Equals("abyss_exit", StringComparison.OrdinalIgnoreCase))
                        await WaitForAbyssHomeAfterNormalExitAsync(ct);
                }
                else if (!step.Type.Equals("wait", StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException($"알 수 없는 step type: {step.Type}");
                }
                return;
            }

            if (!alternativeClicked && step.ClickAlternativeThenWaitPrimary && !string.IsNullOrWhiteSpace(step.AlternativeTarget))
            {
                var alt = await _detector.DetectAsync(step.AlternativeTarget, frame, ct);
                if (alt.Found)
                {
                    Log?.Invoke($"[{step.Name}] 기본 타깃 없음, 대체 타깃 '{step.AlternativeTarget}' 클릭");
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    _input.ClickClientPoint(_hwnd, alt.Center);
                    alternativeClicked = true;
                    await Task.Delay(_settings.ClickSettleMs, ct);
                    continue;
                }
            }

            await Task.Delay(_settings.PollIntervalMs, ct);
        }

        // Optional timeout recovery: click a leave/escape control, click a
        // follow-up confirmation, wait, then restart the scenario cycle.
        if (!string.IsNullOrWhiteSpace(step.TimeoutClickTarget))
        {
            Log?.Invoke($"[{step.Name}] 제한시간 {step.TimeoutSeconds}초 초과 -> 퇴장 절차 시작");
            await ClickTargetWithTimeoutAsync(
                step.TimeoutClickTarget,
                step.TimeoutClickTargetWaitSeconds,
                $"{step.Name} / 던전 퇴장",
                ct);

            if (!string.IsNullOrWhiteSpace(step.TimeoutFollowupClickTarget))
            {
                await ClickTargetWithTimeoutAsync(
                    step.TimeoutFollowupClickTarget,
                    step.TimeoutFollowupWaitSeconds,
                    $"{step.Name} / 나가기",
                    ct);
            }

            if (string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase) &&
                string.Equals(step.TimeoutFollowupClickTarget, "abyss_exit", StringComparison.OrdinalIgnoreCase))
            {
                Log?.Invoke("[어비스] 강제 퇴장 후 던전 밖 복귀 확인");
                await WaitForAbyssHomeAfterNormalExitAsync(ct);
            }

            if (step.TimeoutRestartDelaySeconds > 0)
            {
                Log?.Invoke($"[어비스] 강제 퇴장 완료 및 밖 확인 -> {step.TimeoutRestartDelaySeconds}초 대기 후 처음부터 재시작");
                await Task.Delay(TimeSpan.FromSeconds(step.TimeoutRestartDelaySeconds), ct);
            }

            throw new RestartCycleException();
        }

        Log?.Invoke($"[{step.Name}] TIMEOUT");
        if (_settings.SaveScreenshotOnTimeout)
        {
            try
            {
                Directory.CreateDirectory(Path.Combine(_baseDir, "debug"));
                using var shot = await CaptureGameWindowAsync(ct);
                var path = Path.Combine(_baseDir, "debug", $"timeout_{DateTime.Now:yyyyMMdd_HHmmss}_{Safe(step.Name)}.png");
                shot.Save(path);
                PruneDebugScreenshots();
                Log?.Invoke($"디버그 캡처 저장: {path}");
            }
            catch { }
        }
        // STRICT_CONFIRM_SOFT_TIMEOUT_V1
        if (step.Target.Equals("challenge_confirm_strict", StringComparison.OrdinalIgnoreCase) ||
            step.Name.Contains("도전 최종확인", StringComparison.OrdinalIgnoreCase))
        {
            Log?.Invoke($"[{step.Name}] {step.TimeoutSeconds}초 동안 확인되지 않음 -> 다음 단계 계속");
            return;
        }
        throw new TimeoutException($"'{step.Name}' 단계가 {step.TimeoutSeconds}초 안에 완료되지 않았습니다.");
    }

    private async Task<DetectionResult> DetectAbyssConfirmedClearAsync(Bitmap frame, CancellationToken ct)
    {
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        if (clearTitle.Found && touch.Found)
            return touch;

        if (clearTitle.Score > 0 || touch.Score > 0)
            Log?.Invoke($"[어비스] 클리어 후보 점수: title={clearTitle.Score:0.000}, touch={touch.Score:0.000}");
        return DetectionResult.NotFound;
    }

    private async Task<DetectionResult> DetectAbyssClearVisualAsync(Bitmap frame, CancellationToken ct)
    {
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        if (clearTitle.Found) return clearTitle;
        return await _detector.DetectAsync("abyss_touch_screen", frame, ct);
    }

    private async Task<DetectionResult> WaitForAbyssTouchPromptAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int clearGoneConsecutive = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(20))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
            if (touch.Found)
            {
                Log?.Invoke($"[어비스] 화면 터치 문구 확인 -> 해당 위치 클릭 준비 @ {touch.Bounds}");
                return touch;
            }

            var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
            if (!clearTitle.Found)
            {
                clearGoneConsecutive++;
                if (clearGoneConsecutive >= 3)
                {
                    Log?.Invoke("[어비스] 터치 문구 대기 중 클리어 화면이 이미 3회 연속 사라짐 -> 전환 완료로 처리");
                    return DetectionResult.NotFound;
                }
            }
            else
            {
                clearGoneConsecutive = 0;
            }

            await Task.Delay(Math.Max(200, _settings.PollIntervalMs), ct);
        }

        throw new TimeoutException("어비스 클리어 화면은 감지했지만 '화면을 터치해 주세요' 이미지를 20초 안에 찾지 못했습니다.");
    }

    private async Task WaitForAbyssClearScreenGoneAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int goneConsecutive = 0;
        int retryClicks = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(20))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var clear = await DetectAbyssClearVisualAsync(frame, ct);

            if (!clear.Found)
            {
                goneConsecutive++;
                Log?.Invoke($"[어비스] 클리어 화면 사라짐 확인 {goneConsecutive}/3");
                if (goneConsecutive >= 3)
                {
                    Log?.Invoke("[어비스] 클리어 화면 3회 연속 사라짐 확인 -> 보물상자 단계 진행");
                    return;
                }
            }
            else
            {
                goneConsecutive = 0;

                // If the result screen stayed up, retry once, but still click only the
                // actual touch-prompt image. Never click the clear-title match.
                if (retryClicks < 1 && sw.Elapsed >= TimeSpan.FromSeconds(2))
                {
                    var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
                    if (touch.Found)
                    {
                        _hwnd = await ResolveRequiredGameWindowAsync(ct);
                        NativeMethods.SetForegroundWindow(_hwnd);
                        Log?.Invoke($"[어비스] 클리어 화면 유지 -> 터치 문구 위치 1회 재클릭 @ {touch.Bounds}");
                        _input.ClickClientPoint(_hwnd, touch.Center);
                        retryClicks++;
                        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                        continue;
                    }
                }
            }

            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        throw new TimeoutException("어비스 클리어 화면 클릭 후 화면 전환을 20초 안에 확정하지 못했습니다. 보물상자 단계로 넘어가지 않습니다.");
    }

    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)
    {
        _ = firstDetection; // Recognition proves clear; it is never used as a click position in v67.
        Log?.Invoke("[어비스] 클리어 이미지 2회 확인 완료 -> 터치 문구 이미지를 별도로 찾음");

        var touch = await WaitForAbyssTouchPromptAsync(ct);
        if (!touch.Found)
            return; // The clear screen already disappeared stably while waiting.

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[어비스] '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds}");
        _input.ClickClientPoint(_hwnd, touch.Center);
        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

        // Do not start the 120-second treasure timer after a single missed frame.
        // The result screen must be absent in three consecutive captures first.
        await WaitForAbyssClearScreenGoneAsync(ct);
    }

    private async Task<bool> DetectAbyssOutsideWorkflowAsync(Bitmap frame, CancellationToken ct)
    {
        var home = await _detector.DetectAsync("abyss_outside_home_key", frame, ct);
        var end = await _detector.DetectAsync("abyss_outside_end_key", frame, ct);
        var kHud = await _detector.DetectAsync("abyss_outside_k_hud", frame, ct);
        var iHud = await _detector.DetectAsync("abyss_outside_i_hud", frame, ct);

        int matched =
            (home.Found ? 1 : 0) +
            (end.Found ? 1 : 0) +
            (kHud.Found ? 1 : 0) +
            (iHud.Found ? 1 : 0);

        long now = Environment.TickCount64;
        bool scoreLogDue = _lastAbyssOutsideHudScoreLog == 0 || now - _lastAbyssOutsideHudScoreLog >= 2000;

        if (matched < 3)
        {
            if (scoreLogDue)
            {
                Log?.Invoke(
                    $"[어비스] 던전 밖 HUD 점수 Home={home.Score:0.000} End={end.Score:0.000} K={kHud.Score:0.000} I={iHud.Score:0.000} / 인식={matched}/4 -> 3개 미만");
                _lastAbyssOutsideHudScoreLog = now;
            }
            return false;
        }

        // Three of four fixed outside HUD markers are enough. A clear/result overlay is still
        // explicit dungeon-internal evidence and blocks outside acceptance.
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        bool outside = !clearTitle.Found && !touch.Found;

        if (outside || scoreLogDue)
        {
            Log?.Invoke(
                $"[어비스] 던전 밖 HUD 점수 Home={home.Score:0.000} End={end.Score:0.000} K={kHud.Score:0.000} I={iHud.Score:0.000} / 인식={matched}/4 / Clear={(clearTitle.Found ? 1 : 0)} Touch={(touch.Found ? 1 : 0)} -> {(outside ? "밖 인정" : "클리어 화면으로 보류")}");
            _lastAbyssOutsideHudScoreLog = now;
        }

        return outside;
    }

    private async Task WaitForAbyssHomeAfterNormalExitAsync(CancellationToken ct)
    {
        Log?.Invoke("[어비스] 나가기 클릭 완료 -> 던전 밖 고정 HUD 복귀 확인 중");
        var sw = Stopwatch.StartNew();
        int outsideConsecutive = 0;

        while (sw.Elapsed < TimeSpan.FromSeconds(60))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            if (await DetectAbyssOutsideWorkflowAsync(frame, ct))
            {
                outsideConsecutive++;
                Log?.Invoke($"[어비스] 던전 밖 HUD 3/4 이상 확인 {outsideConsecutive}/3");
                if (outsideConsecutive >= 3)
                {
                    Log?.Invoke("[어비스] 던전 밖 HUD 3회 연속 확인 완료 -> 다음 입장 준비");
                    return;
                }
            }
            else
            {
                outsideConsecutive = 0;
            }
            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        throw new TimeoutException("나가기 후 60초 안에 던전 밖 고정 HUD 4개 중 3개 이상을 확인하지 못했습니다.");
    }

    private async Task ClickTargetWithTimeoutAsync(
        string targetId,
        int timeoutSeconds,
        string label,
        CancellationToken ct)
    {
        Log?.Invoke($"[{label}] 대기: {targetId} / {timeoutSeconds}s");
        var sw = Stopwatch.StartNew();

        while (sw.Elapsed < TimeSpan.FromSeconds(timeoutSeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            if (await CheckMonitorsAsync(frame, ct))
                continue;

            var found = await _detector.DetectAsync(targetId, frame, ct);
            if (found.Found)
            {
                Log?.Invoke($"[{label}] 발견 -> 중앙 클릭: {found.Score:0.000} @ {found.Bounds}");
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                _input.ClickClientPoint(_hwnd, found.Center);
                await Task.Delay(_settings.ClickSettleMs, ct);
                return;
            }

            await Task.Delay(_settings.PollIntervalMs, ct);
        }

        throw new TimeoutException($"'{label}' 타깃 '{targetId}'을(를) {timeoutSeconds}초 안에 찾지 못했습니다.");
    }

    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)
    {
        foreach (var m in _scenario.Monitors)
        {
            long now = Environment.TickCount64;

            if (_monitorLastAction.TryGetValue(m.Target, out var lastAction) &&
                now - lastAction < Math.Max(0, m.CooldownMs))
                continue;

            int scanInterval = Math.Max(0, m.ScanIntervalMs);
            if (scanInterval > 0 &&
                _monitorLastScan.TryGetValue(m.Target, out var lastScan) &&
                now - lastScan < scanInterval)
                continue;
            _monitorLastScan[m.Target] = now;

            var r = await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
            {
                Log?.Invoke($"[monitor] scene_skip 1/2 확인 ({r.ReadText ?? r.Score.ToString("0.000")}) -> 별도 프레임 재확인");
                await Task.Delay(220, ct);
                using var confirmFrame = await CaptureGameWindowAsync(ct);
                var confirm = await _detector.DetectAsync(m.Target, confirmFrame, ct);
                if (!confirm.Found)
                {
                    Log?.Invoke("[monitor] scene_skip 2차 확인 실패 -> 클릭 취소");
                    continue;
                }
                r = confirm;
                Log?.Invoke($"[monitor] scene_skip 2/2 연속 확인 -> 클릭 허용 ({r.ReadText ?? r.Score.ToString("0.000")})");
            }

            _monitorLastAction[m.Target] = Environment.TickCount64;
            switch (m.Action.ToLowerInvariant())
            {
                case "click":
                    Log?.Invoke($"[monitor] {m.Target} 발견 → 클릭 ({r.ReadText ?? r.Score.ToString("0.000")}) @ {r.Bounds}");
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _input.ClickClientPoint(_hwnd, r.Center);
                    await Task.Delay(_settings.ClickSettleMs, ct);
                    return true;
                case "restart_cycle":
                    Log?.Invoke($"[monitor] {m.Target} 발견 → 현재 판 재시작");
                    throw new RestartCycleException();
                case "stop":
                    throw new OperationCanceledException($"감시 타깃 '{m.Target}' 발견으로 정지");
                default:
                    throw new InvalidOperationException($"알 수 없는 monitor action: {m.Action}");
            }
        }
        return false;
    }

    // DUNGEON_FULL_STABILITY_HARDENING_V7
    // HANDLE_RECOVERY_V2
    private async Task<nint> ResolveRequiredGameWindowAsync(CancellationToken ct)
    {
        for (int attempt = 0; attempt < 30; attempt++)
        {
            ct.ThrowIfCancellationRequested();

            if (WindowTools.IsRequiredGameWindow(_hwnd))
                return _hwnd;

            var found = WindowTools.FindRequiredGameWindow();

            if (found != 0)
            {
                if (found != _hwnd)
                {
                    Log?.Invoke(
                        $"마비노기 모바일 창 핸들 재연결: " +
                        $"0x{_hwnd.ToInt64():X} -> 0x{found.ToInt64():X}");
                }

                _hwnd = found;
                return _hwnd;
            }

            if (attempt == 0)
            {
                Log?.Invoke(
                    "마비노기 모바일 창 핸들이 사라졌습니다. " +
                    "새 창을 다시 찾는 중...");
            }

            await Task.Delay(200, ct);
        }

        throw new OperationCanceledException(
            "마비노기 모바일 창을 약 6초 동안 다시 찾지 못해 자동화를 정지합니다.");
    }

    private async Task<Bitmap> CaptureGameWindowAsync(CancellationToken ct)
    {
        Exception? lastError = null;

        for (int attempt = 1; attempt <= 12; attempt++)
        {
            ct.ThrowIfCancellationRequested();

            _hwnd = await ResolveRequiredGameWindowAsync(ct);

            try
            {
                return _capture.CaptureClient(_hwnd);
            }
            catch (Exception ex) when (
                ex is InvalidOperationException ||
                ex is System.ComponentModel.Win32Exception ||
                ex is System.Runtime.InteropServices.ExternalException)
            {
                lastError = ex;

                if (attempt == 1 || attempt == 6)
                {
                    Log?.Invoke(
                        $"화면 캡처 재시도 {attempt}/12: {ex.Message}");
                }

                await Task.Delay(150, ct);
            }
        }

        throw new InvalidOperationException(
            "마비노기 모바일 화면 캡처가 반복해서 실패했습니다.",
            lastError);
    }
    private static string Safe(string s)
    {
        foreach (var c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_');
        return s.Replace(' ', '_');
    }

    public void Dispose() => _input.Dispose();
}
