using System.Diagnostics;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using DungeonVisionBot;

namespace FishingAutomation.Life;

internal sealed class LifeEngine : IDisposable
{
    private readonly AutomationConfig _windowSettings;
    private readonly AppSettings _shared;
    private readonly LifeProfile _profile;
    private readonly AppLog _log;
    private readonly LifeVision _vision;
    private readonly WindowCapture _capture = new();
    private readonly IInputController _mouse;
    private readonly LifeKeyboard _keyboard;
    private readonly int _target;
    private readonly QueuePolicy _queue = new();
    private nint _hwnd;
    private long _frameId, _lastNetworkScan;
    private Rectangle? _avatar, _avatarHud;
    private bool _processing, _gatherNeeded;
    private string _stage = "준비";
    private int _batches, _loops;
    public string InputName => _mouse.ModeName + $" · 생활 keyboard={_keyboard.Device}";
    public event Action<string, int, int, int?>? Progress;

    public LifeEngine(AutomationConfig windowSettings, AppSettings shared, LifeProfile profile,
        string baseDir, int target, AppLog log)
    {
        if (target is < 1 or > 9999) throw new ArgumentOutOfRangeException(nameof(target));
        var errors = profile.Validate(baseDir, windowSettings.ClientWidth, windowSettings.ClientHeight);
        if (errors.Count > 0) throw new InvalidOperationException(string.Join("\n", errors));
        _windowSettings = windowSettings;
        _shared = shared;
        _profile = profile;
        _target = target;
        _log = log;
        _vision = new LifeVision(baseDir, profile);
        try { _keyboard = new LifeKeyboard(windowSettings.InterceptionKeyboardDevice); }
        catch { _vision.Dispose(); throw; }
        try { _mouse = new DungeonVisionBot.InterceptionInput(shared.InterceptionMouseDevice, _keyboard.Device); }
        catch { _keyboard.Dispose(); _vision.Dispose(); throw; }
    }

    public async Task RunAsync(CancellationToken ct)
    {
        int recoveryFailures = 0;
        while (true)
        {
            ct.ThrowIfCancellationRequested();
            try
            {
                await CloseAllAsync(ct);
                if (_gatherNeeded)
                {
                    await GatherAsync(ct);
                    _gatherNeeded = false;
                    _loops++;
                }
                await ProcessingAsync(ct);
                recoveryFailures = 0;
            }
            catch (MaterialsShortException)
            {
                _processing = false;
                _gatherNeeded = true;
                recoveryFailures = 0;
                Stage("재료 부족 · 가공창 닫기");
                // Closing is performed by the next outer iteration with fresh frames.
            }
            catch (Exception ex) when (ex is TimeoutException or LifeRecoveryException)
            {
                _processing = false;
                SaveDebug("recovery");
                int max = _shared.AutoRecoveryEnabled ? Math.Max(1, _shared.AutoRecoveryMaxAttempts) : 0;
                if (++recoveryFailures > max) throw new InvalidOperationException("생활 자동복구 한도 초과: " + ex.Message, ex);
                _avatar = _avatarHud = null;
                _log.Write($"[생활] [자동복구] {recoveryFailures}/{max} · {ex.Message}");
                Stage("자동복구 · 기본 필드 확인");
                await DelayAsync(Math.Max(1, _shared.AutoRecoveryDelaySeconds) * 1000, ct);
            }
        }
    }

    private async Task ProcessingAsync(CancellationToken ct)
    {
        _processing = true;
        Stage("가공 탭 열기");
        await ClickAsync("processing_tab", ct);
        Stage("가공 메뉴 활성화");
        await ClickAsync("processing_menu", ct);
        await StableAsync("processing_active", ct);
        await ClickAsync("cloth_processing", ct);
        Stage("설비로 이동");
        await ClickAsync("move_facility", ct);
        await ClickAsync("cloth_item", ct, _profile.TravelTimeoutSeconds);
        await ClickAsync("go_processing", ct);
        await WaitAsync("queue_anchor", ct);
        await ReconcileEmptyQueueAsync(ct);

        while (true)
        {
            Stage("가공 대기열 채우기 · 7번 슬롯 확인");
            await FillQueueAsync(ct);
            Stage("7번 슬롯 100% 대기");
            var watch = Stopwatch.StartNew();
            while (watch.Elapsed.TotalSeconds < _profile.QueueTimeoutSeconds)
            {
                using var frame = await FrameAsync(ct);
                var anchor = _vision.Find(frame, "queue_anchor");
                if (anchor is { } a)
                {
                    bool occupied = _vision.QueueCloth(frame, 6, a);
                    bool complete = occupied && await _vision.Slot7CompleteAsync(frame, a, ct);
                    if (_queue.CanCollect(occupied, complete, _frameId)) break;
                }
                else _queue.CanCollect(false, false, _frameId);
                await DelayAsync(_profile.PollMs, ct);
            }
            if (watch.Elapsed.TotalSeconds >= _profile.QueueTimeoutSeconds)
                throw new TimeoutException("7번 슬롯 완료 확인 시간 초과");
            Stage("모두 받기 → 확인");
            await ClickAsync("collect_all", ct);
            await ClickAsync("confirm_green", ct);
            await WaitEmptyQueueAsync(ct);
            _queue.ReceivedAndEmpty();
            _batches++;
            Stage("가공 수령 완료 · 다시 채우기");
        }
    }

    private async Task FillQueueAsync(CancellationToken ct)
    {
        var watch = Stopwatch.StartNew();
        while (watch.Elapsed.TotalSeconds < _profile.StepTimeoutSeconds * 7)
        {
            using var frame = await FrameAsync(ct);
            var anchor = _vision.Find(frame, "queue_anchor");
            if (anchor is not { } a) { await DelayAsync(_profile.PollMs, ct); continue; }
            bool seventh = _vision.QueueCloth(frame, 6, a);
            if (!_queue.CanAdd(seventh)) return;
            int before = Enumerable.Range(0, 7).Count(i => _vision.QueueCloth(frame, i, a));
            var add = _vision.Find(frame, "queue_add");
            if (add is null) { await DelayAsync(_profile.PollMs, ct); continue; }
            Click(add.Value, ct);
            await DelayAsync(_profile.SettleMs, ct);
            // A click is acknowledged only by a newly occupied slot (or shortage).
            // A delayed animation never causes blind repeated additions.
            var ack = Stopwatch.StartNew();
            bool increased = false;
            while (ack.Elapsed.TotalSeconds < _profile.StepTimeoutSeconds)
            {
                using var next = await FrameAsync(ct);
                var nextAnchor = _vision.Find(next, "queue_anchor");
                if (nextAnchor is { } b)
                {
                    if (!_queue.CanAdd(_vision.QueueCloth(next, 6, b))) return;
                    int after = Enumerable.Range(0, 7).Count(i => _vision.QueueCloth(next, i, b));
                    if (after > before) { increased = true; break; }
                }
                await DelayAsync(_profile.PollMs, ct);
            }
            if (!increased) throw new TimeoutException("가공 추가 후 새 슬롯이 확인되지 않았습니다.");
        }
        throw new TimeoutException("7번 슬롯까지 가공 대기열을 채우지 못했습니다.");
    }

    private async Task WaitEmptyQueueAsync(CancellationToken ct)
    {
        var confirm = new ConsecutiveConfirmation();
        var watch = Stopwatch.StartNew();
        while (watch.Elapsed.TotalSeconds < _profile.StepTimeoutSeconds)
        {
            using var frame = await FrameAsync(ct);
            var a = _vision.Find(frame, "queue_anchor");
            bool empty = a is not null && Enumerable.Range(0, 7).All(i => !_vision.QueueCloth(frame, i, a.Value));
            if (confirm.Observe(empty, _frameId)) return;
            await DelayAsync(_profile.SettleMs, ct);
        }
        throw new TimeoutException("수령 후 빈 가공 대기열 확인 실패");
    }

    private async Task ReconcileEmptyQueueAsync(CancellationToken ct)
    {
        // After a reconnect/recovery, unlock only if the complete queue is
        // visibly empty in two new captures. Keep the full latch otherwise.
        var empty = new ConsecutiveConfirmation();
        for (int i = 0; i < 2; i++)
        {
            using var frame = await FrameAsync(ct);
            var anchor = _vision.Find(frame, "queue_anchor");
            bool clear = anchor is { } a && Enumerable.Range(0, 7).All(n => !_vision.QueueCloth(frame, n, a));
            if (!clear) return;
            if (empty.Observe(clear, _frameId)) _queue.ReceivedAndEmpty();
            await DelayAsync(_profile.SettleMs, ct);
        }
    }

    private async Task GatherAsync(CancellationToken ct)
    {
        _processing = false;
        Stage("캐릭터 → 생활 스킬");
        await AvatarAsync(ct);
        await ClickAsync("life_skills", ct);
        await ClickAsync("shearing", ct);
        await ClickAsync("sheep", ct);
        await ClickAsync("find_nearby", ct);
        Stage("가까운 양으로 이동 · 채집 게이지 확인");
        await WaitMotionAsync(ct);
        Stage("황금 양털로 자동 채집 진입");
        await OpenItemsAsync(ct);
        await SearchAsync("황금 양털", ct);
        await SelectGoldenAsync(ct);
        await ClickAsync("how_to_get", ct);
        await ClickAsync("golden_shearing", ct);
        await CloseAllAsync(ct);
        await WaitMotionAsync(ct);

        int readFailures = 0;
        while (true)
        {
            Stage($"양털 채집 중 · 목표 {_target}");
            await DelayAsync(_profile.QuantityPollSeconds * 1000, ct);
            await OpenItemsAsync(ct);
            // The preceding golden-wool filter is never reused for ordinary wool.
            await SearchAsync("양털", ct);
            Stage("일반 양털 수량 확인");
            var reached = new ConsecutiveConfirmation();
            int? quantity = null;
            bool targetReached = false;
            for (int i = 0; i < 3; i++)
            {
                using var frame = await FrameAsync(ct);
                // An inactive/changed bag tab invalidates every preceding reading.
                quantity = _vision.Find(frame, "items_active") is null ? null : await _vision.WoolQuantityAsync(frame, ct);
                Progress?.Invoke(_stage, _batches, _loops, quantity);
                if (reached.Observe(quantity is { } q && q >= _target, _frameId)) { targetReached = true; break; }
                if (quantity is not null && quantity < _target) break;
                await DelayAsync(_profile.SettleMs, ct);
            }
            if (quantity is null)
            {
                SaveDebug("wool_ocr");
                if (++readFailures >= 3) throw new TimeoutException("일반 양털 수량 OCR이 3회 연속 실패했습니다.");
            }
            else readFailures = 0;
            Stage(targetReached ? "양털 목표 도달 · 가공으로 복귀" : "가방 닫기 · 채집 계속");
            await ClickAsync("bag_close", ct);
            await StableAsync("field_hud", ct);
            if (targetReached) return;
            await WaitMotionAsync(ct);
        }
    }

    private async Task AvatarAsync(CancellationToken ct)
    {
        using var frame = await FrameAsync(ct);
        var hud = _vision.Find(frame, "field_hud");
        if (hud is null) throw new LifeRecoveryException("캐릭터 메뉴를 열기 전 필드 HUD 확인 실패");
        if (_avatar is null || _avatarHud != hud)
        {
            _avatar = _vision.Find(frame, "avatar_hud");
            _avatarHud = hud;
        }
        if (_avatar is null) throw new TimeoutException("캐릭터 아이콘의 고정 HUD 부분을 찾지 못했습니다.");
        Click(_avatar.Value, ct);
        await DelayAsync(_profile.SettleMs, ct);
        try { await WaitAsync("life_skills", ct); }
        catch (TimeoutException) { _avatar = _avatarHud = null; throw; }
    }

    private async Task OpenItemsAsync(CancellationToken ct)
    {
        await ClickAsync("bag", ct);
        await ClickAsync("items_tab", ct);
        await StableAsync("items_active", ct);
    }

    private async Task SearchAsync(string text, CancellationToken ct)
    {
        await ClickAsync("search_icon", ct);
        var input = await WaitAsync("search_input", ct);
        Click(input, ct);
        await DelayAsync(_profile.SettleMs, ct);
        EnsureInputWindow(ct);
        await _keyboard.ReplaceSearchTextAsync(text, () => EnsureInputWindow(ct), ct);
        EnsureInputWindow(ct);
        _keyboard.Tap(0x1C, ct); // Enter does not replace the mandatory Apply click.
        await DelayAsync(_profile.SettleMs, ct);
        await ClickAsync("search_apply", ct);
        await WaitGoneAsync("search_apply", ct);
        await StableAsync("items_active", ct);
    }

    private async Task SelectGoldenAsync(CancellationToken ct)
    {
        var watch = Stopwatch.StartNew();
        var confirm = new ConsecutiveConfirmation();
        Rectangle? previous = null;
        while (watch.Elapsed.TotalSeconds < _profile.StepTimeoutSeconds)
        {
            using var frame = await FrameAsync(ct);
            var item = await _vision.ExactItemAsync(frame, true, ct);
            bool stable = item is not null && (previous is null || previous == item);
            if (confirm.Observe(stable, _frameId)) { Click(item!.Value, ct); await DelayAsync(_profile.SettleMs, ct); return; }
            previous = item;
            await DelayAsync(_profile.SettleMs, ct);
        }
        throw new TimeoutException("'황금 양털'만 정확하게 확인하지 못했습니다. 황금 양털+는 선택하지 않습니다.");
    }

    private async Task WaitMotionAsync(CancellationToken ct)
    {
        var motion = new GaugeMotion();
        var watch = Stopwatch.StartNew();
        while (watch.Elapsed.TotalSeconds < _profile.TravelTimeoutSeconds)
        {
            using var frame = await FrameAsync(ct);
            if (motion.Observe(_vision.Gauge(frame))) return;
            await DelayAsync(_profile.PollMs, ct);
        }
        throw new TimeoutException("초록색 채집 게이지의 연속 3회 채움 길이 변화 확인 실패");
    }

    private async Task CloseAllAsync(CancellationToken ct)
    {
        _processing = false;
        Stage("창 닫기 · 기본 필드 확인");
        var absent = new ConsecutiveConfirmation();
        var watch = Stopwatch.StartNew();
        int clicks = 0;
        while (watch.Elapsed.TotalSeconds < _profile.StepTimeoutSeconds && clicks < 30)
        {
            using var frame = await FrameAsync(ct);
            var white = _vision.Find(frame, "close_white");
            var gray = _vision.Find(frame, "close_gray");
            var close = white ?? gray;
            if (close is not null)
            {
                absent.Observe(false, _frameId);
                Click(close.Value, ct);
                clicks++;
            }
            else if (absent.Observe(_vision.Find(frame, "field_hud") is not null, _frameId)) return;
            await DelayAsync(_profile.SettleMs, ct);
        }
        throw new TimeoutException("X가 없는 기본 필드를 2회 연속 확인하지 못했습니다.");
    }

    private async Task ClickAsync(string id, CancellationToken ct, int? timeoutSeconds = null)
    {
        var bounds = await WaitAsync(id, ct, timeoutSeconds);
        Click(bounds, ct);
        await DelayAsync(_profile.SettleMs, ct);
    }

    private async Task<Rectangle> WaitAsync(string id, CancellationToken ct, int? timeoutSeconds = null)
    {
        var watch = Stopwatch.StartNew();
        bool capturedStall = false;
        while (watch.Elapsed.TotalSeconds < (timeoutSeconds ?? _profile.StepTimeoutSeconds))
        {
            using var frame = await FrameAsync(ct);
            var found = _vision.Find(frame, id);
            if (found is not null) return found.Value;
            if (!capturedStall && watch.Elapsed.TotalSeconds >= 8) { SaveDebug("stall_" + id); capturedStall = true; }
            await DelayAsync(_profile.PollMs, ct);
        }
        throw new TimeoutException($"{_stage}: {id} 화면 확인 실패");
    }

    private async Task StableAsync(string id, CancellationToken ct)
    {
        var watch = Stopwatch.StartNew();
        var confirmed = new ConsecutiveConfirmation();
        while (watch.Elapsed.TotalSeconds < _profile.StepTimeoutSeconds)
        {
            using var frame = await FrameAsync(ct);
            if (confirmed.Observe(_vision.Find(frame, id) is not null, _frameId)) return;
            await DelayAsync(_profile.SettleMs, ct);
        }
        throw new TimeoutException($"활성/화면 상태 연속 확인 실패: {id}");
    }

    private async Task WaitGoneAsync(string id, CancellationToken ct)
    {
        var watch = Stopwatch.StartNew();
        var absent = new ConsecutiveConfirmation();
        while (watch.Elapsed.TotalSeconds < _profile.StepTimeoutSeconds)
        {
            using var frame = await FrameAsync(ct);
            if (absent.Observe(_vision.Find(frame, id) is null, _frameId)) return;
            await DelayAsync(_profile.SettleMs, ct);
        }
        throw new TimeoutException($"클릭 후 화면 갱신 확인 실패: {id}");
    }

    private async Task<Bitmap> FrameAsync(CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        if (_hwnd == 0)
        {
            var window = WindowLocator.FindAndPrepare(_windowSettings, _log)
                ?? throw new LifeRecoveryException("기존 설정에 맞는 게임 창을 찾을 수 없습니다.");
            _hwnd = window.Handle;
        }
        Bitmap frame;
        try { frame = _capture.CaptureClient(_hwnd); }
        catch (InvalidOperationException ex) { _hwnd = 0; throw new LifeRecoveryException(ex.Message); }
        try
        {
            if (frame.Width != _profile.ClientWidth || frame.Height != _profile.ClientHeight)
            { _hwnd = 0; throw new LifeRecoveryException("게임 창 크기가 변경되었습니다."); }
            _frameId++;
            if (Environment.TickCount64 - _lastNetworkScan >= 1000)
            {
                _lastNetworkScan = Environment.TickCount64;
                var lines = await _vision.ReadAsync(frame, _windowSettings.NetworkRoi.ToRectangle(), 1, ct);
                if (lines.Any(x => LifeRules.NormalizeLabel(x.Text).Contains("운영정책", StringComparison.Ordinal)))
                    throw new InvalidOperationException("운영정책 안내 감지로 생활 매크로를 정지합니다.");
                var retry = lines.FirstOrDefault(x => LifeRules.ExactItem(x.Text, "다시 시도하기"));
                if (!retry.Bounds.IsEmpty)
                {
                    Click(retry.Bounds, ct);
                    _gatherNeeded = false;
                    _log.Write("[생활] 네트워크 재시도 · 처음부터 복귀");
                    await Task.Delay(_profile.SettleMs, ct);
                    throw new LifeRecoveryException("네트워크 연결 재시도 후 화면을 다시 확인합니다.");
                }
            }
            if (_processing && await _vision.MaterialsShortAsync(frame, ct)) throw new MaterialsShortException();
            ct.ThrowIfCancellationRequested();
            return frame;
        }
        catch { frame.Dispose(); throw; }
    }

    private void Click(Rectangle bounds, CancellationToken ct)
    {
        EnsureInputWindow(ct);
        _mouse.ClickClientPoint(_hwnd, new Point(bounds.X + bounds.Width / 2, bounds.Y + bounds.Height / 2));
        ct.ThrowIfCancellationRequested();
    }

    private void EnsureInputWindow(CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        if (_hwnd == 0 || !NativeMethods.GetClientRect(_hwnd, out var r)
            || r.Right - r.Left != _profile.ClientWidth || r.Bottom - r.Top != _profile.ClientHeight)
        { _hwnd = 0; throw new LifeRecoveryException("입력 전 게임 창 재확인이 필요합니다."); }
        NativeMethods.SetForegroundWindow(_hwnd);
        Thread.Sleep(75);
        ct.ThrowIfCancellationRequested();
        if (GetForegroundWindow() != _hwnd)
            throw new LifeRecoveryException("게임 창이 전면에 없어 생활 입력을 취소했습니다.");
    }

    private async Task DelayAsync(int ms, CancellationToken ct)
    {
        var watch = Stopwatch.StartNew();
        while (watch.ElapsedMilliseconds < ms)
        {
            await Task.Delay(Math.Min(250, Math.Max(1, ms - (int)watch.ElapsedMilliseconds)), ct);
            // Long gathering waits still check cancellation, capture health and reconnect notices.
            if (ms >= 5000 && watch.ElapsedMilliseconds % 1000 < 300)
                using (await FrameAsync(ct)) { }
        }
    }

    private void Stage(string text)
    {
        _stage = text;
        _log.Write("[생활] " + text);
        Progress?.Invoke(text, _batches, _loops, null);
    }

    private void SaveDebug(string reason)
    {
        if (!_shared.SaveScreenshotOnTimeout || _hwnd == 0) return;
        try
        {
            string folder = Path.Combine(AppContext.BaseDirectory, _windowSettings.DebugFolder, "life");
            Directory.CreateDirectory(folder);
            using var frame = _capture.CaptureClient(_hwnd);
            frame.Save(Path.Combine(folder, $"{DateTime.Now:yyyyMMdd_HHmmss_fff}_{reason}.png"), ImageFormat.Png);
        }
        catch (Exception ex) { _log.Write("[생활] 이상 화면 저장 실패: " + ex.Message); }
    }

    public void Dispose() { _mouse.Dispose(); _keyboard.Dispose(); _vision.Dispose(); }
    [DllImport("user32.dll")] private static extern nint GetForegroundWindow();
    private sealed class MaterialsShortException : Exception;
    private sealed class LifeRecoveryException(string message) : Exception(message);
}
