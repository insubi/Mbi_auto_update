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
# 1) Explicit Abyss state machine. This file contains no detector thresholds,
#    ROIs, click coordinates, or input choices.
# ---------------------------------------------------------------------------
state_path = app / "dungeon" / "ScenarioEngine.AbyssState.cs"
state_path.write_text(r'''namespace DungeonVisionBot;

internal sealed partial class ScenarioEngine
{
    private enum AbyssFlowState
    {
        Unknown = 0,
        CombatClearWait,
        ClearConfirmed,
        TouchReady,
        TouchClicked,
        ResultConfirmed,
        RetryClicked,
        Reentering
    }

    private readonly object _abyssFlowStateLock = new();
    private AbyssFlowState _abyssFlowState = AbyssFlowState.Unknown;

    private static bool AbyssCanTransition(AbyssFlowState from, AbyssFlowState to)
    {
        if (from == to)
            return true;

        return (from, to) switch
        {
            // A direct confirmed clear/result screen is valid during recovery,
            // where the process may attach after the normal earlier states.
            (AbyssFlowState.Unknown, AbyssFlowState.CombatClearWait) => true,
            (AbyssFlowState.Unknown, AbyssFlowState.ClearConfirmed) => true,
            (AbyssFlowState.Unknown, AbyssFlowState.ResultConfirmed) => true,

            (AbyssFlowState.CombatClearWait, AbyssFlowState.ClearConfirmed) => true,
            (AbyssFlowState.CombatClearWait, AbyssFlowState.ResultConfirmed) => true,

            (AbyssFlowState.ClearConfirmed, AbyssFlowState.TouchReady) => true,
            (AbyssFlowState.ClearConfirmed, AbyssFlowState.ResultConfirmed) => true,

            (AbyssFlowState.TouchReady, AbyssFlowState.TouchClicked) => true,
            (AbyssFlowState.TouchReady, AbyssFlowState.ResultConfirmed) => true,

            (AbyssFlowState.TouchClicked, AbyssFlowState.ResultConfirmed) => true,

            (AbyssFlowState.ResultConfirmed, AbyssFlowState.RetryClicked) => true,
            (AbyssFlowState.RetryClicked, AbyssFlowState.Reentering) => true,
            (AbyssFlowState.Reentering, AbyssFlowState.CombatClearWait) => true,

            _ => false
        };
    }

    private AbyssFlowState GetAbyssFlowState()
    {
        lock (_abyssFlowStateLock)
            return _abyssFlowState;
    }

    private string AbyssFlowStateText()
    {
        return GetAbyssFlowState().ToString();
    }

    private void AbyssResetFlowState(string reason)
    {
        if (!IsAbyss)
            return;

        AbyssFlowState previous;
        lock (_abyssFlowStateLock)
        {
            previous = _abyssFlowState;
            _abyssFlowState = AbyssFlowState.Unknown;
        }

        Log?.Invoke($"[어비스 상태] RESET {previous} -> Unknown · {reason}");
    }

    private void AbyssTransitionTo(AbyssFlowState next, string reason)
    {
        if (!IsAbyss)
            return;

        AbyssFlowState previous;
        lock (_abyssFlowStateLock)
        {
            previous = _abyssFlowState;
            if (!AbyssCanTransition(previous, next))
            {
                throw new InvalidOperationException(
                    $"어비스 상태 전이 차단: {previous} -> {next} · {reason}");
            }

            _abyssFlowState = next;
        }

        if (previous != next)
            Log?.Invoke($"[어비스 상태] {previous} -> {next} · {reason}");
    }

    private void AbyssRequireState(AbyssFlowState expected, string operation)
    {
        if (!IsAbyss)
            return;

        AbyssFlowState current = GetAbyssFlowState();
        if (current != expected)
        {
            throw new InvalidOperationException(
                $"어비스 상태 불일치로 입력 차단: operation={operation}, expected={expected}, actual={current}");
        }
    }

    private void AbyssEnterCombatClearWait(string reason)
    {
        if (!IsAbyss)
            return;

        AbyssFlowState current = GetAbyssFlowState();
        if (current == AbyssFlowState.CombatClearWait)
            return;

        AbyssTransitionTo(AbyssFlowState.CombatClearWait, reason);
    }
}
''', encoding="utf-8", newline="\n")

# ---------------------------------------------------------------------------
# 2) Wire the state machine into the EXISTING state observations/actions.
#    Existing detection/click behavior is preserved.
# ---------------------------------------------------------------------------
engine = app / "dungeon" / "ScenarioEngine.cs"
s = read(engine)

# Reset only when a full menu-start cycle begins. A retry cycle resumes at combat step.
old = '''            int startStep = Math.Clamp(_resumeStepIndex, 0, maxStep);
            bool resuming = _resumeStepIndex > 0;
            _resumeStepIndex = 0;

            _cycle++;
'''
new = '''            int startStep = Math.Clamp(_resumeStepIndex, 0, maxStep);
            bool resuming = _resumeStepIndex > 0;
            _resumeStepIndex = 0;

            if (IsAbyss && startStep == 0)
                AbyssResetFlowState(resuming ? "전체 사이클 복구 재시작" : "새 어비스 사이클");

            _cycle++;
'''
if old not in s:
    raise SystemExit("RunAsync cycle anchor missing")
s = s.replace(old, new, 1)

# Step 5 is the existing combat-clear wait. This does not add any new detector.
old = '''    private async Task ExecuteStepAsync(ScenarioStep step, CancellationToken ct)
    {
        DiagnosticSetStage(step.Target, step.Name);

        if (IsAbyss && step.Target == "abyss_result_retry")
'''
new = '''    private async Task ExecuteStepAsync(ScenarioStep step, CancellationToken ct)
    {
        DiagnosticSetStage(step.Target, step.Name);

        if (IsAbyss && step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
            AbyssEnterCombatClearWait("5단계 전투 종료/클리어 화면 대기 시작");

        if (IsAbyss && step.Target == "abyss_result_retry")
'''
if old not in s:
    raise SystemExit("ExecuteStepAsync entry anchor missing")
s = s.replace(old, new, 1)

# Existing fast path: if result is already visible, record the actual observed state.
old = '''                // A result screen may already be open if the clear overlay was dismissed.
                if ((await DetectAbyssResultRetryAsync(frame, ct)).Found)
                    return;
                found = await DetectAbyssConfirmedClearAsync(frame, ct);
'''
new = '''                // A result screen may already be open if the clear overlay was dismissed.
                var alreadyResult = await DetectAbyssResultRetryAsync(frame, ct);
                if (alreadyResult.Found)
                {
                    AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "5단계에서 실제 결과 화면을 먼저 확인");
                    return;
                }
                found = await DetectAbyssConfirmedClearAsync(frame, ct);
'''
if old not in s:
    raise SystemExit("Step 5 existing result fast-path anchor missing")
s = s.replace(old, new, 1)

# Clear is a state only after BOTH existing production targets are confirmed.
old = '''        if (clearTitle.Found && touch.Found)
            return touch;
'''
new = '''        if (clearTitle.Found && touch.Found)
        {
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "클리어 타이틀 + 화면 터치 문구 동시 확인");
            return touch;
        }
'''
if old not in s:
    raise SystemExit("confirmed clear anchor missing")
s = s.replace(old, new, 1)

# Touch wait may only skip touch if actual result screen is already visible.
old = '''            if (result.Found)
            {
                Log?.Invoke("[어비스] 터치 문구 대기 중 실제 결과 화면 확인 -> 추가 터치 없이 결과 단계 진행");
                return DetectionResult.NotFound;
            }

            var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
            if (touch.Found)
            {
                Log?.Invoke($"[어비스] 화면 터치 문구 확인 -> 해당 위치 클릭 준비 @ {touch.Bounds}");
                return touch;
            }
'''
new = '''            if (result.Found)
            {
                AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "터치 대기 중 실제 결과 화면 확인");
                Log?.Invoke("[어비스] 터치 문구 대기 중 실제 결과 화면 확인 -> 추가 터치 없이 결과 단계 진행");
                return DetectionResult.NotFound;
            }

            var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
            if (touch.Found)
            {
                AbyssTransitionTo(AbyssFlowState.TouchReady, "화면 터치 문구 확인");
                Log?.Invoke($"[어비스] 화면 터치 문구 확인 -> 해당 위치 클릭 준비 @ {touch.Bounds}");
                return touch;
            }
'''
if old not in s:
    raise SystemExit("touch/result wait anchor missing")
s = s.replace(old, new, 1)

old = '''                    var safeTouch = new Rectangle(360, 915, 80, 60);
                    Log?.Invoke($"[어비스] 클리어 타이틀 2회 확인 + 터치 문구 미검출 -> 안전 터치 위치 사용 @ {safeTouch}");
                    return new DetectionResult(true, safeTouch, clearTitle.Score, "clear_touch_safe_fallback");
'''
new = '''                    var safeTouch = new Rectangle(360, 915, 80, 60);
                    AbyssTransitionTo(AbyssFlowState.TouchReady, "클리어 타이틀 2회 확인 + 기존 안전 터치 fallback");
                    Log?.Invoke($"[어비스] 클리어 타이틀 2회 확인 + 터치 문구 미검출 -> 안전 터치 위치 사용 @ {safeTouch}");
                    return new DetectionResult(true, safeTouch, clearTitle.Score, "clear_touch_safe_fallback");
'''
if old not in s:
    raise SystemExit("safe touch fallback anchor missing")
s = s.replace(old, new, 1)

# Waiting for the result screen is legal only after the clear-screen touch was clicked.
old = '''    private async Task WaitForAbyssClearScreenGoneAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
'''
new = '''    private async Task WaitForAbyssClearScreenGoneAsync(CancellationToken ct)
    {
        AbyssRequireState(AbyssFlowState.TouchClicked, "클리어 화면 클릭 후 결과 화면 대기");

        var sw = Stopwatch.StartNew();
'''
if old not in s:
    raise SystemExit("clear-screen-gone method anchor missing")
s = s.replace(old, new, 1)

old = '''            if (result.Found)
            {
                Log?.Invoke($"[어비스] 실제 결과 화면 확인 -> 다시 하기 단계 진행 @ {result.Bounds}");
                return;
            }
'''
new = '''            if (result.Found)
            {
                AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "클리어 화면 클릭 후 실제 결과 화면 확인");
                Log?.Invoke($"[어비스] 실제 결과 화면 확인 -> 다시 하기 단계 진행 @ {result.Bounds}");
                return;
            }
'''
if old not in s:
    raise SystemExit("result confirmation in clear-gone anchor missing")
s = s.replace(old, new, 1)

# Advance: confirmed clear -> touch ready -> click -> touch clicked.
old = '''    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)
    {
        // DetectAbyssConfirmedClearAsync returns the touch-prompt detection itself after
        // clear-title + touch are simultaneously confirmed. Use that confirmed point
        // immediately instead of throwing it away and trying to detect the prompt again.
        var touch = firstDetection.Found ? firstDetection : await WaitForAbyssTouchPromptAsync(ct);

        if (!touch.Found)
        {
            // NotFound is allowed only when WaitForAbyssTouchPromptAsync already proved
            // that the real result screen is visible.
            Log?.Invoke("[어비스] 실제 결과 화면이 이미 확인됨 -> 클리어 터치 생략");
            return;
        }

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[어비스] 확인된 '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds} source={touch.ReadText}");
        DiagnosticObserveClick("abyss_clear_touch", touch.Center);
        _input.ClickClientPoint(_hwnd, touch.Center);
        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

        // Step 5 is not complete until the actual result screen is confirmed.
        await WaitForAbyssClearScreenGoneAsync(ct);
    }
'''
new = '''    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)
    {
        // DetectAbyssConfirmedClearAsync returns the touch-prompt detection itself after
        // clear-title + touch are simultaneously confirmed. Use that confirmed point
        // immediately instead of throwing it away and trying to detect the prompt again.
        if (firstDetection.Found)
        {
            AbyssTransitionTo(AbyssFlowState.ClearConfirmed, "클리어 화면 확정 결과를 터치 단계로 전달");
            AbyssTransitionTo(AbyssFlowState.TouchReady, "확정된 터치 문구 위치 사용");
        }

        var touch = firstDetection.Found ? firstDetection : await WaitForAbyssTouchPromptAsync(ct);

        if (!touch.Found)
        {
            // NotFound is allowed only when WaitForAbyssTouchPromptAsync already proved
            // that the real result screen is visible.
            AbyssRequireState(AbyssFlowState.ResultConfirmed, "클리어 터치 생략");
            Log?.Invoke("[어비스] 실제 결과 화면이 이미 확인됨 -> 클리어 터치 생략");
            return;
        }

        // No touch input is permitted unless the state machine reached TouchReady.
        AbyssRequireState(AbyssFlowState.TouchReady, "클리어 화면 터치");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[어비스] 확인된 '화면을 터치해 주세요' 위치 클릭 @ {touch.Bounds} source={touch.ReadText}");
        DiagnosticObserveClick("abyss_clear_touch", touch.Center);
        _input.ClickClientPoint(_hwnd, touch.Center);
        AbyssTransitionTo(AbyssFlowState.TouchClicked, "클리어 화면 터치 입력 완료");
        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

        // Step 5 is not complete until the actual result screen is confirmed.
        await WaitForAbyssClearScreenGoneAsync(ct);
    }
'''
if old not in s:
    raise SystemExit("AdvanceAbyssClearScreenAsync full anchor missing")
s = s.replace(old, new, 1)

write(engine, s)

# ---------------------------------------------------------------------------
# 3) Result retry: actual result confirmation is mandatory before click,
#    then explicit RetryClicked -> Reentering -> CombatClearWait.
# ---------------------------------------------------------------------------
retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
r = read(retry_path)

old = '''            if (retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds))
            {
                ct.ThrowIfCancellationRequested();
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");
                DiagnosticObserveClick("abyss_result_retry", retry.Center);
                _input.ClickClientPoint(_hwnd, retry.Center);
                await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                await WaitForAbyssRetryTransitionAsync(ct);
                return;
            }
'''
new = '''            if (retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds))
            {
                // Two consecutive production detections are the authority for ResultConfirmed.
                AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "다시 하기 결과 화면 2회 연속 확인");
                AbyssRequireState(AbyssFlowState.ResultConfirmed, "다시 하기 클릭");

                ct.ThrowIfCancellationRequested();
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[어비스] 아래 중앙 다시 하기 2회 연속 확인 -> 다시 하기만 클릭 @ {retry.Center} source={retry.ReadText} safe={AbyssRetrySafeRoi}");
                DiagnosticObserveClick("abyss_result_retry", retry.Center);
                _input.ClickClientPoint(_hwnd, retry.Center);
                AbyssTransitionTo(AbyssFlowState.RetryClicked, "가운데 다시 하기 클릭 완료");
                await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);
                AbyssTransitionTo(AbyssFlowState.Reentering, "다시 하기 클릭 후 결과 화면 이탈 대기");
                await WaitForAbyssRetryTransitionAsync(ct);
                return;
            }
'''
if old not in r:
    raise SystemExit("RetryAbyssResultAsync click block anchor missing")
r = r.replace(old, new, 1)

old = '''    private async Task WaitForAbyssRetryTransitionAsync(CancellationToken ct)
    {
        var timer = Stopwatch.StartNew();
'''
new = '''    private async Task WaitForAbyssRetryTransitionAsync(CancellationToken ct)
    {
        AbyssRequireState(AbyssFlowState.Reentering, "다시 하기 후 재입장 전환 확인");

        var timer = Stopwatch.StartNew();
'''
if old not in r:
    raise SystemExit("WaitForAbyssRetryTransitionAsync entry anchor missing")
r = r.replace(old, new, 1)

old = '''                if (++gone >= 3)
                {
                    Log?.Invoke("[어비스] 다시 하기 결과 화면 이탈 확인 -> 선택 화면 없이 전투 대기로 복귀");
                    return;
                }
'''
new = '''                if (++gone >= 3)
                {
                    // Preserve the existing V0.1.58 transition rule exactly:
                    // retry screen absent for 3 frames and no entry/outside screen.
                    AbyssTransitionTo(
                        AbyssFlowState.CombatClearWait,
                        "결과 화면 3회 연속 이탈 + 입장/필드 화면 아님");
                    Log?.Invoke("[어비스] 다시 하기 결과 화면 이탈 확인 -> 선택 화면 없이 전투 대기로 복귀");
                    return;
                }
'''
if old not in r:
    raise SystemExit("retry transition completion anchor missing")
r = r.replace(old, new, 1)

# Include current state in existing failure message without changing failure behavior.
old = '''            $"나가기/다른 던전 가기로 우회하지 않습니다. 진단: {_lastAbyssResultDiagnostic}; {DiagnosticSummary()}");
'''
new = '''            $"나가기/다른 던전 가기로 우회하지 않습니다. 상태={AbyssFlowStateText()}; 진단: {_lastAbyssResultDiagnostic}; {DiagnosticSummary()}");
'''
if old not in r:
    raise SystemExit("retry failure diagnostic anchor missing")
r = r.replace(old, new, 1)

write(retry_path, r)

# ---------------------------------------------------------------------------
# 4) Version metadata.
# ---------------------------------------------------------------------------
project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.58</Version>", "<Version>0.1.59</Version>"),
    ("<AssemblyVersion>0.1.58.0</AssemblyVersion>", "<AssemblyVersion>0.1.59.0</AssemblyVersion>"),
    ("<FileVersion>0.1.58.0</FileVersion>", "<FileVersion>0.1.59.0</FileVersion>"),
):
    if old not in p:
        raise SystemExit(f"project version marker missing: {old}")
    p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.58"' not in u:
    raise SystemExit("UpdateManager V0.1.58 marker missing")
u = u.replace('CurrentVersion = "V0.1.58"', 'CurrentVersion = "V0.1.59"', 1)
write(update, u)

# ---------------------------------------------------------------------------
# 5) Static invariants.
# ---------------------------------------------------------------------------
state = read(state_path)
engine_text = read(engine)
retry_text = read(retry_path)

for marker in (
    'private enum AbyssFlowState',
    'CombatClearWait',
    'ClearConfirmed',
    'TouchReady',
    'TouchClicked',
    'ResultConfirmed',
    'RetryClicked',
    'Reentering',
    'private static bool AbyssCanTransition',
    '어비스 상태 전이 차단',
    '어비스 상태 불일치로 입력 차단',
):
    if marker not in state:
        raise SystemExit(f"state machine marker missing: {marker}")

for marker in (
    'AbyssEnterCombatClearWait("5단계 전투 종료/클리어 화면 대기 시작")',
    'AbyssTransitionTo(AbyssFlowState.ClearConfirmed',
    'AbyssRequireState(AbyssFlowState.TouchReady',
    'AbyssTransitionTo(AbyssFlowState.TouchClicked',
    'AbyssRequireState(AbyssFlowState.TouchClicked',
    'AbyssTransitionTo(AbyssFlowState.ResultConfirmed',
    'Step 5 is not complete until the actual result screen is confirmed.',
):
    if marker not in engine_text:
        raise SystemExit(f"ScenarioEngine state wiring missing: {marker}")

for marker in (
    'retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds)',
    'AbyssRequireState(AbyssFlowState.ResultConfirmed',
    'AbyssTransitionTo(AbyssFlowState.RetryClicked',
    'AbyssTransitionTo(AbyssFlowState.Reentering',
    'AbyssRequireState(AbyssFlowState.Reentering',
    'AbyssFlowState.CombatClearWait',
    '_input.ClickClientPoint(_hwnd, retry.Center);',
):
    if marker not in retry_text:
        raise SystemExit(f"AbyssRetry state wiring missing: {marker}")

# Existing V0.1.55 visual result behavior must remain untouched.
for marker in (
    'ScaleAbyssResultRoi',
    'GetGreenButtonRatio',
    'aspect < 0.74 || aspect > 0.86',
    'exitGreen < 0.18 || retryGreen < 0.18 || otherGreen < 0.18',
    'visual_result_button_row',
):
    if marker not in retry_text:
        raise SystemExit(f"V0.1.55 result detector behavior lost: {marker}")

if "<Version>0.1.59</Version>" not in read(project):
    raise SystemExit("project version not V0.1.59")
if 'CurrentVersion = "V0.1.59"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.59")

print("V0.1.59 applied: explicit Abyss state machine, existing detectors/coordinates preserved")
