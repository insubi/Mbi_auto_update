#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0131_peaca_auto_route.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
main_path = app / "MainForm.cs"
refui_path = app / "MainForm.ReferenceUI.cs"
dash_path = app / "MainForm.Dashboard.cs"
input_path = app / "dungeon" / "InputController.cs"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
targets_path = app / "dungeon" / "config" / "targets.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"patch anchor missing: {label}")
    return text.replace(old, new, 1)

# ---------------- MainForm.cs ----------------
main = read(main_path)
main = replace_once(
    main,
    '    private readonly ComboBox _mode = new();\n    private readonly ComboBox _abyssDungeon = new();\n',
    '    private readonly ComboBox _mode = new();\n    private readonly ComboBox _dungeonDestination = new();\n    private readonly ComboBox _abyssDungeon = new();\n',
    'dungeon destination field')

main = replace_once(
    main,
    '    private string SelectedMode => _mode.SelectedItem?.ToString() ?? "낚시";\n    private string SelectedAbyssDungeon => _abyssDungeon.SelectedItem?.ToString() ?? "허상의 정박지";\n',
    '''    private string SelectedMode => _mode.SelectedItem?.ToString() ?? "낚시";
    private string SelectedDungeonDestination => _dungeonDestination.SelectedItem?.ToString() ?? "현재 위치";
    private string? SelectedDungeonPreRoute => SelectedDungeonDestination switch
    {
        "페카 심층 1-1" => "peaca_d1_1",
        "페카 심층 2-2" => "peaca_d2_2",
        _ => null
    };
    private string SelectedAbyssDungeon => _abyssDungeon.SelectedItem?.ToString() ?? "허상의 정박지";
''',
    'selected dungeon properties')

abyss_event = '''        _abyssDungeon.SelectedIndexChanged += (_, _) =>
        {
            if (_activeMode is null && SelectedMode == "어비스")
            {
                _log.Write($"[어비스] 선택 던전: {SelectedAbyssDungeon}");
                RefreshModeStatus();
            }
        };
'''
main = replace_once(
    main,
    abyss_event,
    '''        _dungeonDestination.SelectedIndexChanged += (_, _) =>
        {
            if (_activeMode is null && SelectedMode == "던전")
            {
                _log.Write($"[던전] 선택 던전: {SelectedDungeonDestination}");
                RefreshModeStatus();
                UpdateDashboard();
            }
        };

''' + abyss_event,
    'dungeon destination event')

main = replace_once(
    main,
    '            var engine = new ScenarioEngine(window.Handle, settings, scenario, targets, baseDir);\n',
    '''            string? preRoute = modeName == "던전" ? SelectedDungeonPreRoute : null;
            if (modeName == "던전")
                _log.Write($"[던전] 시작 대상={SelectedDungeonDestination}" + (preRoute is null ? " · 현재 위치에서 시작" : " · 자동 맵 이동 사용"));

            var engine = new ScenarioEngine(window.Handle, settings, scenario, targets, baseDir, preRoute);
''',
    'ScenarioEngine pre-route wiring')

write(main_path, main)

# ---------------- Reference UI ----------------
refui = read(refui_path)
refui = replace_once(
    refui,
    '        _mode.Items.AddRange(new object[] { "낚시", "던전", "어비스" });\n        _mode.SelectedIndex = 0;\n        _abyssDungeon.Items.AddRange(new object[] { "허상의 정박지", "광기의 동굴", "흩어진 물길" });\n',
    '        _mode.Items.AddRange(new object[] { "낚시", "던전", "어비스" });\n        _mode.SelectedIndex = 0;\n        _dungeonDestination.Items.AddRange(new object[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-2" });\n        _dungeonDestination.SelectedIndex = 0;\n        _abyssDungeon.Items.AddRange(new object[] { "허상의 정박지", "광기의 동굴", "흩어진 물길" });\n',
    'reference UI dungeon items')

select_dungeon_anchor = '''        private void SelectDungeon(int index)
        {
            _owner.SafeUiAction("어비스 던전 선택", () =>
'''
refui = replace_once(
    refui,
    select_dungeon_anchor,
    '''        private void SelectRegularDungeon(int index)
        {
            _owner.SafeUiAction("던전 선택", () =>
            {
                if (_owner.AnyRunning || _owner._activeMode is not null) return;
                if (index < 0 || index >= _owner._dungeonDestination.Items.Count) return;
                _owner._mode.SelectedIndex = 1;
                _owner._dungeonDestination.SelectedIndex = index;
                _owner.UpdateDashboard();
            });
        }

''' + select_dungeon_anchor,
    'regular dungeon selector method')

old_menu = '''        private void ShowDungeonMenu()
        {
            if (_owner.AnyRunning || _owner._activeMode is not null) return;

            // 허상의 정박지 / 광기의 동굴 / 흩어진 물길은 모두 어비스 전용이다.
            // 현재 모드가 낚시 또는 던전이면 선택 던전 버튼을 눌러도
            // 아무 메뉴도 표시하지 않는다. 왼쪽 낚시/던전 버튼으로
            // 모드를 바꾼 경우에도 동일하게 적용된다.
            if (!string.Equals(_owner._mode.SelectedItem?.ToString(), "어비스", StringComparison.Ordinal))
                return;

            ShowMenu(new[] { "허상의 정박지", "광기의 동굴", "흩어진 물길" }, SelectDungeon, 680, 312);
        }
'''
new_menu = '''        private void ShowDungeonMenu()
        {
            if (_owner.AnyRunning || _owner._activeMode is not null) return;

            string mode = _owner._mode.SelectedItem?.ToString() ?? "";
            if (string.Equals(mode, "던전", StringComparison.Ordinal))
            {
                ShowMenu(new[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-2" }, SelectRegularDungeon, 680, 312);
                return;
            }

            if (string.Equals(mode, "어비스", StringComparison.Ordinal))
            {
                ShowMenu(new[] { "허상의 정박지", "광기의 동굴", "흩어진 물길" }, SelectDungeon, 680, 312);
            }
        }
'''
refui = replace_once(refui, old_menu, new_menu, 'dungeon menu branching')
write(refui_path, refui)

# ---------------- Dashboard display ----------------
dash = read(dash_path)
dash = replace_once(
    dash,
    '''        bool idle = !AnyRunning && _activeMode is null;
        bool abyss = (_activeMode ?? SelectedMode) == "어비스";
        _currentModeValue.Text = _activeMode ?? SelectedMode;
        _currentDungeonValue.Text = abyss ? SelectedAbyssDungeon : "—";
''',
    '''        bool idle = !AnyRunning && _activeMode is null;
        string displayMode = _activeMode ?? SelectedMode;
        bool abyss = displayMode == "어비스";
        bool dungeon = displayMode == "던전";
        _currentModeValue.Text = displayMode;
        _currentDungeonValue.Text = abyss ? SelectedAbyssDungeon : dungeon ? SelectedDungeonDestination : "—";
''',
    'dashboard selected dungeon display')

dash = replace_once(
    dash,
    '        _miniInfo.Text = $"{(abyss ? SelectedAbyssDungeon : _activeMode ?? SelectedMode)} · {_stageTime.Text}";\n',
    '        _miniInfo.Text = $"{(abyss ? SelectedAbyssDungeon : dungeon ? SelectedDungeonDestination : displayMode)} · {_stageTime.Text}";\n',
    'mini selected dungeon display')
write(dash_path, dash)

# ---------------- Interception drag support ----------------
inp = read(input_path)
inp = replace_once(
    inp,
    '''    string ModeName { get; }
    void ClickClientPoint(nint hwnd, Point clientPoint);
    void TapScanCode(ushort scanCode);
''',
    '''    string ModeName { get; }
    void ClickClientPoint(nint hwnd, Point clientPoint);
    void DragClientPoint(nint hwnd, Point startClientPoint, Point endClientPoint, int durationMs);
    void TapScanCode(ushort scanCode);
''',
    'input drag interface')

click_end = '''        Thread.Sleep(30);
    }

    public void TapScanCode(ushort scanCode)
'''
drag_method = '''        Thread.Sleep(30);
    }

    public void DragClientPoint(nint hwnd, Point startClientPoint, Point endClientPoint, int durationMs)
    {
        if (hwnd == 0) throw new InvalidOperationException("게임 창 핸들이 없습니다.");
        var origin = new NativeMethods.POINT { X = 0, Y = 0 };
        if (!NativeMethods.ClientToScreen(hwnd, ref origin))
            throw new InvalidOperationException("게임 창 좌표를 화면 좌표로 변환하지 못했습니다.");

        int sx = origin.X + startClientPoint.X;
        int sy = origin.Y + startClientPoint.Y;
        int ex = origin.X + endClientPoint.X;
        int ey = origin.Y + endClientPoint.Y;
        NativeMethods.SetForegroundWindow(hwnd);
        Thread.Sleep(100);
        SendAbsolute(_mouseDevice, sx, sy);
        Thread.Sleep(90);
        SendMouse(_mouseDevice, new InterceptionMouseStroke { state = MOUSE_LEFT_DOWN });
        Thread.Sleep(80);

        int steps = Math.Clamp(Math.Max(8, durationMs / 40), 8, 30);
        int delay = Math.Max(15, durationMs / steps);
        for (int i = 1; i <= steps; i++)
        {
            double t = i / (double)steps;
            int x = (int)Math.Round(sx + (ex - sx) * t);
            int y = (int)Math.Round(sy + (ey - sy) * t);
            SendAbsolute(_mouseDevice, x, y);
            Thread.Sleep(delay);
        }

        SendMouse(_mouseDevice, new InterceptionMouseStroke { state = MOUSE_LEFT_UP });
        Thread.Sleep(120);
        if (!GetCursorPos(out var actual) || Math.Abs(actual.X - ex) > 8 || Math.Abs(actual.Y - ey) > 8)
            throw new InvalidOperationException($"Interception 드래그 후 커서 검증 실패: target=({ex},{ey}) cursor=({actual.X},{actual.Y})");
    }

    public void TapScanCode(ushort scanCode)
'''
inp = replace_once(inp, click_end, drag_method, 'Interception drag implementation')

fallback_anchor = '''    public void TapScanCode(ushort scanCode)
    {
        throw new InvalidOperationException(
            "SendInput fallback은 비활성화되어 있습니다.");
    }
'''
fallback_new = '''    public void DragClientPoint(nint hwnd, Point startClientPoint, Point endClientPoint, int durationMs)
    {
        throw new InvalidOperationException(
            "SendInput fallback은 비활성화되어 있습니다. 지도 드래그는 Interception으로만 전송합니다.");
    }

''' + fallback_anchor
inp = replace_once(inp, fallback_anchor, fallback_new, 'fallback drag implementation')
write(input_path, inp)

# ---------------- ScenarioEngine route ----------------
engine = read(engine_path)
engine = replace_once(
    engine,
    '    private readonly string _baseDir;\n',
    '    private readonly string _baseDir;\n    private readonly string? _preRoute;\n',
    'pre-route field')
engine = replace_once(
    engine,
    '    public ScenarioEngine(nint hwnd, AppSettings settings, ScenarioDefinition scenario, List<TargetDefinition> targets, string baseDir)\n',
    '    public ScenarioEngine(nint hwnd, AppSettings settings, ScenarioDefinition scenario, List<TargetDefinition> targets, string baseDir, string? preRoute = null)\n',
    'ScenarioEngine constructor signature')
engine = replace_once(
    engine,
    '''        _baseDir = baseDir;
        _detector = new TargetDetector(targets, baseDir);
''',
    '''        _baseDir = baseDir;
        _preRoute = preRoute;
        _detector = new TargetDetector(targets, baseDir);
''',
    'pre-route constructor assignment')
engine = replace_once(
    engine,
    '''    public async Task RunAsync(CancellationToken ct)
    {
        Log?.Invoke($"입력 모드: {InputMode}");
        int recoveryFailures = 0;
''',
    '''    public async Task RunAsync(CancellationToken ct)
    {
        Log?.Invoke($"입력 모드: {InputMode}");
        if (!string.IsNullOrWhiteSpace(_preRoute))
            await RunPeacaPreRouteAsync(_preRoute!, ct);

        int recoveryFailures = 0;
''',
    'pre-route RunAsync hook')

route_methods = r'''    // PEACA_AUTO_ROUTE_V1
    private async Task RunPeacaPreRouteAsync(string route, CancellationToken ct)
    {
        bool d11 = route.Equals("peaca_d1_1", StringComparison.OrdinalIgnoreCase);
        bool d22 = route.Equals("peaca_d2_2", StringComparison.OrdinalIgnoreCase);
        if (!d11 && !d22)
            throw new InvalidOperationException($"지원하지 않는 던전 자동 이동 경로: {route}");

        string destination = d11 ? "페카 심층 1-1" : "페카 심층 2-2";
        Log?.Invoke($"[페카 자동이동] 시작 -> {destination}");
        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);

        // Already-open map is accepted. Otherwise M is sent exactly once and verified.
        using (var first = await CaptureGameWindowAsync(ct))
        {
            var mapOpen = await _detector.DetectAsync("route_ulla_continent", first, ct);
            if (!mapOpen.Found)
            {
                Log?.Invoke("[페카 자동이동] M 입력 -> 지도 열기");
                _input.TapScanCode(0x32); // M
                await Task.Delay(1000, ct);
            }
        }

        DetectionResult ulla;
        using (var mapFrame = await CaptureGameWindowAsync(ct))
            ulla = await _detector.DetectAsync("route_ulla_continent", mapFrame, ct);
        if (!ulla.Found)
            throw new TimeoutException("M 입력 후 좌측 상단 '울라 대륙'을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[페카 자동이동] 울라 대륙 확인 -> 클릭 @ {ulla.Bounds}");
        _input.ClickClientPoint(_hwnd, ulla.Center);
        await Task.Delay(1000, ct);

        await AlignWorldMapTopLeftAsync(ct);
        var peaca = await FindPeacaOnWorldMapAsync(ct);
        if (!peaca.Found)
            throw new TimeoutException("울라 대륙 지도를 제한 범위까지 탐색했지만 '페카 고분'을 찾지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[페카 자동이동] 페카 고분 OCR 발견 -> 글자 위치 클릭 @ {peaca.Bounds}");
        _input.ClickClientPoint(_hwnd, peaca.Center);
        await Task.Delay(700, ct);

        bool popupReady = await WaitForTargetPairAsync("route_peaca_popup_title", "route_go_here", 8, ct);
        if (!popupReady)
            throw new TimeoutException("페카 고분 클릭 후 '페카 고분 + 여기로 가기' 확인에 실패했습니다. Space를 누르지 않습니다.");

        Log?.Invoke("[페카 자동이동] 페카 고분 + 여기로 가기 확인 -> Space");
        _input.TapScanCode(0x39); // Space

        bool arrived = await WaitForTargetPairAsync("route_peaca_title", "route_deep_tab", 30, ct);
        if (!arrived)
            throw new TimeoutException("이동 후 30초 안에 페카 고분 도착/심층 던전 탭을 확인하지 못했습니다.");

        DetectionResult deepTab;
        using (var arrivedFrame = await CaptureGameWindowAsync(ct))
            deepTab = await _detector.DetectAsync("route_deep_tab", arrivedFrame, ct);
        if (!deepTab.Found)
            throw new TimeoutException("페카 고분 도착 후 심층 던전 탭을 다시 확인하지 못했습니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        Log?.Invoke($"[페카 자동이동] 심층 던전 탭 클릭 @ {deepTab.Bounds}");
        _input.ClickClientPoint(_hwnd, deepTab.Center);
        await Task.Delay(900, ct);

        string slotTarget = d11 ? "route_d1_1" : "route_d2_2";
        string enterTarget = d11 ? "route_enter_d1_1" : "route_enter_d2_2";
        var slot = await WaitForTargetAsync(slotTarget, 10, ct);
        if (!slot.Found)
            throw new TimeoutException($"{destination} 구역 표기를 10초 안에 찾지 못했습니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        Log?.Invoke($"[페카 자동이동] {destination} 구역 OCR 확인 -> 클릭 @ {slot.Bounds}");
        _input.ClickClientPoint(_hwnd, slot.Center);
        await Task.Delay(650, ct);

        var enter = await WaitForTargetAsync(enterTarget, 8, ct);
        if (!enter.Found)
            throw new TimeoutException($"{destination} 선택 후 정확한 진입 문구를 확인하지 못했습니다. Space를 누르지 않습니다.");

        Log?.Invoke($"[페카 자동이동] {destination} 진입 문구 확인 -> Space");
        _input.TapScanCode(0x39);

        var handoff = await WaitForTargetAsync("enter_bottom", 20, ct);
        if (!handoff.Found)
            throw new TimeoutException("심층 구역 진입 후 기존 던전 매크로 초입 '입장하기' 화면을 20초 안에 확인하지 못했습니다.");

        Log?.Invoke("[페카 자동이동] 기존 던전 매크로 초입 확인 완료 -> 기존 선택됨/도전/입장 로직으로 인계");
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
                Log?.Invoke($"[페카 자동이동] 동시 확인: {firstId} + {secondId}");
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
        Log?.Invoke("[페카 자동이동] 울라 월드맵 좌상단 끝 정렬 시작");

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
            Log?.Invoke($"[페카 자동이동] 좌상단 정렬 {attempt}/12 · 화면변화={diff:0.00} · 끝판정={stable}/2");
            if (stable >= 2)
            {
                Log?.Invoke("[페카 자동이동] 화면 변화 거의 없음 2회 연속 -> 좌상단 끝 도달 확정");
                return;
            }
        }

        throw new TimeoutException("월드맵을 좌상단 끝으로 정렬하지 못했습니다. 12회 제한 후 정지합니다.");
    }

    private async Task<DetectionResult> FindPeacaOnWorldMapAsync(CancellationToken ct)
    {
        const double EdgeThreshold = 6.0;
        bool moveViewportRight = true;
        Log?.Invoke("[페카 자동이동] 좌상단 기준 지그재그 탐색 시작");

        for (int row = 0; row < 4; row++)
        {
            int edgeStable = 0;
            for (int col = 0; col < 6; col++)
            {
                ct.ThrowIfCancellationRequested();
                using var frame = await CaptureGameWindowAsync(ct);
                var found = await _detector.DetectAsync("route_peaca_map", frame, ct);
                if (found.Found)
                {
                    Log?.Invoke($"[페카 자동이동] 페카 고분 발견 row={row + 1}, col={col + 1} @ {found.Bounds}");
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
                Log?.Invoke($"[페카 자동이동] 가로 탐색 row={row + 1}, step={col + 1} · 화면변화={diff:0.00} · 경계={edgeStable}/2");
                if (edgeStable >= 2) break;
            }

            using (var last = await CaptureGameWindowAsync(ct))
            {
                var found = await _detector.DetectAsync("route_peaca_map", last, ct);
                if (found.Found) return found;
            }
            if (row == 3) break;

            using var beforeDown = await CaptureGameWindowAsync(ct);
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            _input.DragClientPoint(_hwnd, new Point(380, 650), new Point(380, 320), 850);
            await Task.Delay(650, ct);
            using var afterDown = await CaptureGameWindowAsync(ct);
            double downDiff = MapFrameDifference(beforeDown, afterDown);
            Log?.Invoke($"[페카 자동이동] 다음 줄 이동 {row + 1}-> {row + 2} · 화면변화={downDiff:0.00}");
            if (downDiff <= EdgeThreshold)
            {
                // One confirmation drag avoids treating a transient low-change frame as the bottom edge.
                using var confirmBefore = await CaptureGameWindowAsync(ct);
                _input.DragClientPoint(_hwnd, new Point(380, 650), new Point(380, 320), 850);
                await Task.Delay(650, ct);
                using var confirmAfter = await CaptureGameWindowAsync(ct);
                double confirmDiff = MapFrameDifference(confirmBefore, confirmAfter);
                Log?.Invoke($"[페카 자동이동] 세로 경계 재확인 · 화면변화={confirmDiff:0.00}");
                if (confirmDiff <= EdgeThreshold) break;
            }
            moveViewportRight = !moveViewportRight;
        }

        return DetectionResult.NotFound;
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

'''
engine = replace_once(
    engine,
    '    private int FindDungeonStepIndex(string targetId)\n',
    route_methods + '    private int FindDungeonStepIndex(string targetId)\n',
    'Peaca route methods insertion')
write(engine_path, engine)

# ---------------- Route OCR targets ----------------
targets = json.loads(read(targets_path))
route_targets = [
    {"Id":"route_ulla_continent","Kind":"ocr","Roi":{"X":0,"Y":0,"Width":330,"Height":140},"Text":"울라 대륙","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_peaca_map","Kind":"ocr","Roi":{"X":20,"Y":110,"Width":660,"Height":650},"Text":"페카 고분","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_peaca_popup_title","Kind":"ocr","Roi":{"X":100,"Y":500,"Width":600,"Height":300},"Text":"페카 고분","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_go_here","Kind":"ocr","Roi":{"X":80,"Y":790,"Width":640,"Height":210},"Text":"여기로 가기","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_peaca_title","Kind":"ocr","Roi":{"X":0,"Y":0,"Width":300,"Height":170},"Text":"페카 고분","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_deep_tab","Kind":"ocr","Roi":{"X":40,"Y":70,"Width":360,"Height":170},"Text":"심층 던전","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_d1_1","Kind":"ocr","Roi":{"X":160,"Y":390,"Width":380,"Height":280},"Text":"D1-1","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_d2_2","Kind":"ocr","Roi":{"X":180,"Y":680,"Width":420,"Height":280},"Text":"D2-2","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_enter_d1_1","Kind":"ocr","Roi":{"X":80,"Y":830,"Width":640,"Height":170},"Text":"심층 1층 1구역 진입","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_enter_d2_2","Kind":"ocr","Roi":{"X":80,"Y":830,"Width":640,"Height":170},"Text":"심층 2층 2구역 진입","MaxEditDistance":2,"OcrRetryAt2x":True},
]
ids = {x["Id"] for x in route_targets}
targets = [x for x in targets if x.get("Id") not in ids] + route_targets
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Runtime version bump while preserving unrelated feature identifiers.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.30", "V0.1.31")
                   .replace("0.1.30.0", "0.1.31.0")
                   .replace("0.1.30", "0.1.31"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.31_PEACA_AUTO_ROUTE.txt").write_text(
    "MABI AUTO V0.1.31 - PEACA AUTO ROUTE TEST\n\n"
    "Adds dungeon selector entries: current position, Peaca Deep D1-1, Peaca Deep D2-2.\n"
    "For Peaca selections: M -> Ula continent -> deterministic top-left map anchor -> bounded serpentine OCR search for Peaca Tomb -> verify Peaca Tomb + Go Here -> Space -> Deep Dungeon -> D1-1/D2-2 -> verify exact entry text -> Space -> existing dungeon challenge/entry loop.\n"
    "Top-left edge is accepted only after two consecutive low-change map drags. Search never guesses a fallback target and stops after bounded attempts.\n"
    "Existing V0.1.30 dungeon/Abyss/fishing behavior is preserved; policy/ERROR88 OCR detection remains removed.\n",
    encoding="utf-8"
)

print("V0.1.31 patch applied: Peaca D1-1/D2-2 auto-route + existing dungeon handoff")
