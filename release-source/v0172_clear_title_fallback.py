#!/usr/bin/env python3
from pathlib import Path
import hashlib, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
timeout_path = app / "dungeon" / "ScenarioEngine.AbyssTimeout.cs"
project_path = app / "FishingAutomation.csproj"
update_path = app / "UpdateManager.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
           {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
before = {p.relative_to(root).as_posix(): digest(p) for p in tracked}

engine = read(engine_path)

field_anchor = '''    private int _resumeStepIndex;
'''
field_replace = '''    private int _resumeStepIndex;

    // V0172_ABYSS_CLEAR_TITLE_FALLBACK
    // The real clear screen can show a stable "던전 클리어!" title while the bottom
    // "화면을 터치해 주세요" template scores below its 0.68 threshold.
    // Keep the strict title+touch path first, then allow a guarded 2-frame title fallback.
    private int _abyssClearTitleFallbackConsecutive;
    private const double AbyssClearTitleFallbackMinScore = 0.68;
    private const int AbyssClearTitleFallbackRequiredFrames = 2;
    private static readonly Rectangle AbyssClearSafeTouch = new(360, 915, 80, 60);
    private bool AbyssClearTitleFallbackPending => _abyssClearTitleFallbackConsecutive > 0;
'''
if engine.count(field_anchor) != 1:
    raise SystemExit("ScenarioEngine field anchor mismatch")
engine = engine.replace(field_anchor, field_replace, 1)

old_clear = '''    private async Task<DetectionResult> DetectAbyssConfirmedClearAsync(Bitmap frame, CancellationToken ct)
    {
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        DiagnosticObserveDetection("abyss_dungeon_clear_visual", clearTitle);
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        DiagnosticObserveDetection("abyss_touch_screen", touch);
        if (clearTitle.Found && touch.Found)
        {
            ResetAbyssExitState(true);
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "클리어 타이틀 + 화면 터치 문구 동시 확인");
            return touch;
        }

        // V0164_ABYSS_CLEAR_LOG_SIMPLIFIED:
        // Suppress ordinary combat similarity noise. This affects logging only.
        const double ClearCandidateLogThreshold = 0.65;
        if (clearTitle.Score >= ClearCandidateLogThreshold || touch.Score >= ClearCandidateLogThreshold)
            Log?.Invoke($"[어비스] 강한 클리어 후보: title={clearTitle.Score:0.000}, touch={touch.Score:0.000}");
        return DetectionResult.NotFound;
    }
'''
new_clear = '''    private async Task<DetectionResult> DetectAbyssConfirmedClearAsync(Bitmap frame, CancellationToken ct)
    {
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        DiagnosticObserveDetection("abyss_dungeon_clear_visual", clearTitle);
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        DiagnosticObserveDetection("abyss_touch_screen", touch);

        // Preferred path: both independent clear signals are visible in the same frame.
        if (clearTitle.Found && touch.Found)
        {
            _abyssClearTitleFallbackConsecutive = 0;
            ResetAbyssExitState(true);
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "클리어 타이틀 + 화면 터치 문구 동시 확인");
            return touch;
        }

        // V0.1.72 fallback:
        // In real captures the title stayed around 0.69~0.75 while the touch template
        // fluctuated around 0.48~0.63. Do not lower the global touch threshold.
        // Instead, on the canonical 800x1000 client require a strong clear title in
        // two consecutive frames and then use the already-established safe touch point
        // centered at (400,945).
        bool titleFallbackCandidate =
            frame.Width == 800 &&
            frame.Height == 1000 &&
            clearTitle.Found &&
            clearTitle.Score >= AbyssClearTitleFallbackMinScore;

        if (titleFallbackCandidate)
        {
            _abyssClearTitleFallbackConsecutive++;
            if (_abyssClearTitleFallbackConsecutive >= AbyssClearTitleFallbackRequiredFrames)
            {
                _abyssClearTitleFallbackConsecutive = 0;
                ResetAbyssExitState(true);
                AbyssTransitionTo(
                    AbyssFlowState.ClearConfirmed,
                    "클리어 타이틀 강한 신호 2프레임 + 안전 터치 fallback");
                Log?.Invoke(
                    $"[어비스] 클리어 타이틀 강한 신호 2/2 확인 " +
                    $"title={clearTitle.Score:0.000}, touch={touch.Score:0.000} " +
                    $"-> 안전 터치 위치 사용 @ {AbyssClearSafeTouch}");
                return new DetectionResult(
                    true,
                    AbyssClearSafeTouch,
                    clearTitle.Score,
                    "clear_title_2x_safe_fallback");
            }

            Log?.Invoke(
                $"[어비스] 클리어 타이틀 강한 신호 1/2 " +
                $"title={clearTitle.Score:0.000}, touch={touch.Score:0.000} -> 퇴장/모니터 입력 보류");
        }
        else
        {
            _abyssClearTitleFallbackConsecutive = 0;
        }

        // V0164_ABYSS_CLEAR_LOG_SIMPLIFIED:
        // Suppress ordinary combat similarity noise. This affects logging only.
        const double ClearCandidateLogThreshold = 0.65;
        if (clearTitle.Score >= ClearCandidateLogThreshold || touch.Score >= ClearCandidateLogThreshold)
            Log?.Invoke($"[어비스] 강한 클리어 후보: title={clearTitle.Score:0.000}, touch={touch.Score:0.000}");
        return DetectionResult.NotFound;
    }
'''
if engine.count(old_clear) != 1:
    raise SystemExit("DetectAbyssConfirmedClearAsync anchor mismatch")
engine = engine.replace(old_clear, new_clear, 1)

old_recovery = '''            var clearVisual = await DetectAbyssConfirmedClearAsync(frame, ct);
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
'''
new_recovery = '''            var clearVisual = await DetectAbyssConfirmedClearAsync(frame, ct);
            if (clearVisual.Found)
            {
                clearScreenSeen = true;
                clearTransitionConfirmed = false;
                clearGoneConsecutive = 0;

                // Use the already-confirmed point directly. This is either the real touch
                // template or the guarded V0.1.72 safe fallback centered at (400,945).
                if (now - lastTouchClick >= 1800)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    touchClicks++;
                    Log?.Invoke(
                        $"[어비스 자동복구] 클리어 화면 확인 완료 -> 화면 터치 {touchClicks}회 " +
                        $"@ {clearVisual.Bounds} source={clearVisual.ReadText}");
                    _input.ClickClientPoint(_hwnd, clearVisual.Center);
                    lastTouchClick = now;
                    await Task.Delay(Math.Max(900, _settings.ClickSettleMs), ct);
                    continue;
                }
                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                continue;
            }
'''
if engine.count(old_recovery) != 1:
    raise SystemExit("Abyss recovery clear block anchor mismatch")
engine = engine.replace(old_recovery, new_recovery, 1)

write(engine_path, engine)

timeout = read(timeout_path)

old_late_clear = '''    private async Task<bool> HandleAbyssLateClearAsync(Bitmap frame, CancellationToken ct)
    {
        // Check the touch prompt before every exit input, including the confirmation.
        // A visible prompt alone must veto an exit even if the title template misses.
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        if (touch.Found)
        {
            ResetAbyssExitState(true);
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "10분 경계에서 화면 터치 문구 확인");
            await AdvanceAbyssClearScreenAsync(touch, ct);
            return true;
        }
        var result = await DetectAbyssResultRetryAsync(frame, ct);
        if (result.Found)
        {
            ResetAbyssExitState(true);
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "10분 경계에서 실제 결과 화면 확인");
            AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "기존 결과 처리로 연결");
            return true;
        }
        return false;
    }
'''
new_late_clear = '''    private async Task<bool> HandleAbyssLateClearAsync(Bitmap frame, CancellationToken ct)
    {
        // Check the touch prompt before every exit input, including the confirmation.
        // A visible prompt alone must veto an exit even if the title template misses.
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        if (touch.Found)
        {
            _abyssClearTitleFallbackConsecutive = 0;
            ResetAbyssExitState(true);
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "10분 경계에서 화면 터치 문구 확인");
            await AdvanceAbyssClearScreenAsync(touch, ct);
            return true;
        }

        // The first strong-title frame only arms the fallback and blocks exit input.
        // The second consecutive strong-title frame returns the safe touch rectangle.
        var confirmedClear = await DetectAbyssConfirmedClearAsync(frame, ct);
        if (confirmedClear.Found)
        {
            ResetAbyssExitState(true);
            Log?.Invoke("[어비스 타임아웃] 클리어 타이틀 fallback 확정 -> 강제 퇴장 취소");
            await AdvanceAbyssClearScreenAsync(confirmedClear, ct);
            return true;
        }

        var result = await DetectAbyssResultRetryAsync(frame, ct);
        if (result.Found)
        {
            _abyssClearTitleFallbackConsecutive = 0;
            ResetAbyssExitState(true);
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "10분 경계에서 실제 결과 화면 확인");
            AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "기존 결과 처리로 연결");
            return true;
        }
        return false;
    }
'''
if timeout.count(old_late_clear) != 1:
    raise SystemExit("HandleAbyssLateClearAsync anchor mismatch")
timeout = timeout.replace(old_late_clear, new_late_clear, 1)

old_exit_guard = '''                    using var frame = await CaptureGameWindowAsync(ct);
                    if (await HandleAbyssLateClearAsync(frame, ct)) return;
                    var target = await _detector.DetectAsync(action.Target, frame, ct);
'''
new_exit_guard = '''                    using var frame = await CaptureGameWindowAsync(ct);
                    if (await HandleAbyssLateClearAsync(frame, ct)) return;

                    // One strong clear-title frame is enough to veto this frame's exit input.
                    // The next fresh frame must confirm 2/2 before the safe clear touch is sent.
                    if (AbyssClearTitleFallbackPending)
                    {
                        Log?.Invoke("[어비스 타임아웃] 클리어 타이틀 후보 확인 중 -> 퇴장 입력 보류");
                        await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                        continue;
                    }

                    var target = await _detector.DetectAsync(action.Target, frame, ct);
'''
if timeout.count(old_exit_guard) != 1:
    raise SystemExit("Abyss timeout exit guard anchor mismatch")
timeout = timeout.replace(old_exit_guard, new_exit_guard, 1)

write(timeout_path, timeout)

project = read(project_path)
for old, new in (
    ("<Version>0.1.71</Version>", "<Version>0.1.72</Version>"),
    ("<AssemblyVersion>0.1.71.0</AssemblyVersion>", "<AssemblyVersion>0.1.72.0</AssemblyVersion>"),
    ("<FileVersion>0.1.71.0</FileVersion>", "<FileVersion>0.1.72.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.71"' not in update:
    raise SystemExit("UpdateManager V0.1.71 marker missing")
update = update.replace('CurrentVersion = "V0.1.71"', 'CurrentVersion = "V0.1.72"', 1)
write(update_path, update)

# Scope and behavior verification.
after_tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                 {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
after = {p.relative_to(root).as_posix(): digest(p) for p in after_tracked}
changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
allowed = {
    engine_path.relative_to(root).as_posix(),
    timeout_path.relative_to(root).as_posix(),
    project_path.relative_to(root).as_posix(),
    update_path.relative_to(root).as_posix(),
}
unexpected = sorted(changed - allowed)
if unexpected:
    raise SystemExit("unexpected V0.1.72 changes: " + ", ".join(unexpected))

engine_check = read(engine_path)
timeout_check = read(timeout_path)
all_runtime = "\n".join(read(p) for p in (app / "dungeon").glob("ScenarioEngine*.cs"))

for marker in (
    "V0172_ABYSS_CLEAR_TITLE_FALLBACK",
    "AbyssClearTitleFallbackMinScore = 0.68",
    "AbyssClearTitleFallbackRequiredFrames = 2",
    "AbyssClearSafeTouch = new(360, 915, 80, 60)",
    "clear_title_2x_safe_fallback",
    "클리어 타이틀 강한 신호 2/2 확인",
):
    if marker not in engine_check:
        raise SystemExit(f"V0.1.72 engine marker missing: {marker}")

for marker in (
    "클리어 타이틀 후보 확인 중 -> 퇴장 입력 보류",
    "클리어 타이틀 fallback 확정 -> 강제 퇴장 취소",
    "AbyssClearTitleFallbackPending",
):
    if marker not in timeout_check:
        raise SystemExit(f"V0.1.72 timeout marker missing: {marker}")

# Preserve strict primary detection and existing result/loot behavior.
for marker in (
    "if (clearTitle.Found && touch.Found)",
    "실제 결과 화면 2/2 확인",
    "DetectAbyssResultRetryAsync",
    "[어비스 전리품]",
    "LootStats.RecordRound",
):
    if marker not in all_runtime:
        raise SystemExit(f"preserved behavior marker missing: {marker}")

# Death-specific logic must stay removed.
for p in app.rglob("*"):
    if p.suffix.lower() in (".cs", ".json"):
        text = read(p)
        if re.search(r"abyss_death|AbyssDeath|DeathTimeout|사망", text):
            raise SystemExit(f"death logic returned: {p}")

scenario = __import__("json").loads(read(app / "abyss" / "config" / "scenario.json"))
combat = next(s for s in scenario["Steps"] if s["Target"] == "abyss_touch_screen")
if combat["TimeoutSeconds"] != 600:
    raise SystemExit("Abyss combat timeout is not 600 seconds")

print("PASS V0.1.72: guarded clear-title fallback + timeout veto; death removed; loot/result preserved")
