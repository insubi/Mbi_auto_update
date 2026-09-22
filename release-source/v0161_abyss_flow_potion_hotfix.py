#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

# This script runs AFTER v0161_abyss_retry_potion_fix.py.
# It only hardens the Abyss combat->result transition and the remaining
# smart-recovery potion-popup path.

state_path = app / "dungeon" / "ScenarioEngine.AbyssState.cs"
state = read(state_path)
direct_transition = "            (AbyssFlowState.CombatClearWait, AbyssFlowState.ResultConfirmed) => true,\n"
if direct_transition not in state:
    raise SystemExit("CombatClearWait -> ResultConfirmed transition anchor missing")
state = state.replace(direct_transition, "", 1)
write(state_path, state)

engine_path = app / "dungeon" / "ScenarioEngine.cs"
engine = read(engine_path)

fast_path = """                // A result screen may already be open if the clear overlay was dismissed.
                var alreadyResult = await DetectAbyssResultRetryAsync(frame, ct);
                if (alreadyResult.Found)
                {
                    AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "5단계에서 실제 결과 화면을 먼저 확인");
                    return;
                }
"""
if fast_path not in engine:
    raise SystemExit("step-5 result fast-path anchor missing")
engine = engine.replace(fast_path, "", 1)

wait_vars = """        var sw = Stopwatch.StartNew();
        int retryClicks = 0;
        int clearTitleConsecutive = 0;
"""
wait_vars_new = """        var sw = Stopwatch.StartNew();
        int retryClicks = 0;
        int clearTitleConsecutive = 0;
        DetectionResult previousResult = DetectionResult.NotFound;
"""
if wait_vars not in engine:
    raise SystemExit("post-touch result wait variable anchor missing")
engine = engine.replace(wait_vars, wait_vars_new, 1)

single_result = """            var result = await DetectAbyssResultRetryAsync(frame, ct);
            if (result.Found)
            {
                AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "클리어 화면 클릭 후 실제 결과 화면 확인");
                Log?.Invoke($"[어비스] 실제 결과 화면 확인 -> 다시 하기 단계 진행 @ {result.Bounds}");
                return;
            }
"""
stable_result = """            var result = await DetectAbyssResultRetryAsync(frame, ct);
            if (result.Found)
            {
                if (previousResult.Found && result.Bounds.IntersectsWith(previousResult.Bounds))
                {
                    AbyssTransitionTo(AbyssFlowState.ResultConfirmed, "클리어 화면 클릭 후 실제 결과 화면 2프레임 연속 확인");
                    Log?.Invoke($"[어비스] 실제 결과 화면 2/2 확인 -> 다시 하기 단계 진행 @ {result.Bounds}");
                    return;
                }

                previousResult = result;
                Log?.Invoke($"[어비스] 실제 결과 화면 후보 1/2 @ {result.Bounds}");
                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                continue;
            }
            previousResult = DetectionResult.NotFound;
"""
if single_result not in engine:
    raise SystemExit("single-frame post-touch result confirmation anchor missing")
engine = engine.replace(single_result, stable_result, 1)

old_recovery_popup = """            if (now - lastPopupClick >= 2500)
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
"""
new_recovery_popup = """            if (now - lastPopupClick >= 2500)
            {
                var popupTitle = await _detector.DetectAsync("abyss_potion_popup_title", frame, ct);
                var popupClose = await _detector.DetectAsync("abyss_popup_close", frame, ct);
                if (popupTitle.Found || popupClose.Found)
                {
                    string popupSource = popupTitle.Found ? "title-ocr" : "close-template";
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[어비스 자동복구] 회복 물약 팝업 확인({popupSource}) -> 마우스 클릭 없이 ESC 1회");
                    _input.TapScanCode(0x01);
                    lastPopupClick = now;

                    var popupTimer = Stopwatch.StartNew();
                    int popupGoneFrames = 0;
                    while (popupTimer.Elapsed < TimeSpan.FromSeconds(4))
                    {
                        ct.ThrowIfCancellationRequested();
                        await Task.Delay(180, ct);
                        using var popupCheck = await CaptureGameWindowAsync(ct);
                        var titleAfter = await _detector.DetectAsync("abyss_potion_popup_title", popupCheck, ct);
                        var closeAfter = await _detector.DetectAsync("abyss_popup_close", popupCheck, ct);
                        if (titleAfter.Found || closeAfter.Found)
                        {
                            popupGoneFrames = 0;
                            continue;
                        }

                        if (++popupGoneFrames >= 2)
                        {
                            Log?.Invoke("[어비스 자동복구] 회복 물약 팝업 ESC 후 닫힘 2프레임 확인");
                            break;
                        }
                    }

                    if (popupGoneFrames < 2)
                    {
                        Log?.Invoke("[어비스 자동복구] 회복 물약 팝업 ESC 후 닫힘 확인 실패 -> 구매/닫기 좌표 클릭 없이 복구 실패 처리");
                        return false;
                    }

                    continue;
                }
            }
"""
if old_recovery_popup not in engine:
    raise SystemExit("legacy Abyss recovery popup mouse-click block missing")
engine = engine.replace(old_recovery_popup, new_recovery_popup, 1)
write(engine_path, engine)

# Static safety checks.
state = read(state_path)
engine = read(engine_path)
if direct_transition in state:
    raise SystemExit("CombatClearWait -> ResultConfirmed direct transition still present")
if "5단계에서 실제 결과 화면을 먼저 확인" in engine:
    raise SystemExit("step-5 result fast-path still present")
for marker in (
    "DetectionResult previousResult = DetectionResult.NotFound;",
    "실제 결과 화면 후보 1/2",
    "실제 결과 화면 2/2 확인",
    "result.Bounds.IntersectsWith(previousResult.Bounds)",
    "회복 물약 팝업 확인({popupSource}) -> 마우스 클릭 없이 ESC 1회",
    "회복 물약 팝업 ESC 후 닫힘 2프레임 확인",
):
    if marker not in engine:
        raise SystemExit(f"hardening marker missing: {marker}")
if "팝업 닫기 이미지 확인 -> 클릭" in engine:
    raise SystemExit("legacy Abyss recovery popup mouse-click path still present")

print("V0.1.61 hardening applied: no combat->result fast-path, 2-frame result confirm, recovery popup ESC")
