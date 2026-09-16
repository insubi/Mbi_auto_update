#!/usr/bin/env python3
from pathlib import Path
import base64, json, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0122_dungeon_selected_and_state_recovery.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
scenario_path = app / "dungeon" / "config" / "scenario.json"
targets_path = app / "dungeon" / "config" / "targets.json"
tpl_dir = app / "dungeon" / "templates"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

# Red '선택됨' text crop supplied from the 2026-09-16 failure screenshot.
selected_red_b64 = "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"
tpl_dir.mkdir(parents=True, exist_ok=True)
(tpl_dir / "selected_red_visual.png").write_bytes(base64.b64decode(selected_red_b64))

# Restore the intended dungeon rule: selected -> click -> challenge confirmed -> enter.
scenario = json.loads(read(scenario_path))
step1 = scenario["Steps"][0]
step1["Name"] = "1. 도전 상태 확인"
step1["Type"] = "wait"
step1["Target"] = "challenge"
step1["TimeoutSeconds"] = 45
step1["AlternativeTarget"] = "selected"
step1["ClickAlternativeThenWaitPrimary"] = True
write(scenario_path, json.dumps(scenario, ensure_ascii=False, indent=2) + "\n")

# Red selected state: template first + OCR fallback. This keeps the same logic for all colors.
targets = json.loads(read(targets_path))
selected = next((t for t in targets if t.get("Id") == "selected"), None)
if selected is None:
    raise RuntimeError("selected target missing")
selected["Kind"] = "hybrid"
selected["TemplatePath"] = "templates/selected_red_visual.png"
selected["Threshold"] = 0.70
selected["TemplateScaleMin"] = 0.72
selected["TemplateScaleMax"] = 1.30
selected["TemplateScaleStep"] = 0.04
selected["Text"] = "선택됨"
selected["MaxEditDistance"] = 1
selected["OcrRetryAt2x"] = True
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

engine = read(engine_path)

# State-aware resume fields.
field_marker = "    private long _lastAbyssOutsideHudScoreLog;\n"
if field_marker not in engine:
    raise RuntimeError("engine field marker missing")
engine = engine.replace(field_marker, field_marker + "    private int _currentStepIndex;\n    private int _resumeStepIndex;\n", 1)

# Replace RunAsync through the TrySmartRecovery marker.
run_start = engine.find("    public async Task RunAsync(CancellationToken ct)\n")
smart_start = engine.find("    private async Task<bool> TrySmartRecoveryAsync(CancellationToken ct)\n")
if run_start < 0 or smart_start < 0 or smart_start <= run_start:
    raise RuntimeError("RunAsync/TrySmartRecovery markers missing")

new_run = '''    public async Task RunAsync(CancellationToken ct)
    {
        Log?.Invoke($"입력 모드: {InputMode}");
        int recoveryFailures = 0;
        do
        {
            int startStep = Math.Clamp(_resumeStepIndex, 0, Math.Max(0, _scenario.Steps.Count - 1));
            bool resumed = _resumeStepIndex > 0;
            _resumeStepIndex = 0;

            _cycle++;
            Log?.Invoke(resumed
                ? $"===== {_cycle}판 복구 재개: {startStep + 1}. {_scenario.Steps[startStep].Name} ====="
                : $"===== {_cycle}판 시작 =====");

            try
            {
                for (int i = startStep; i < _scenario.Steps.Count; i++)
                {
                    _currentStepIndex = i;
                    ct.ThrowIfCancellationRequested();
                    await ExecuteStepAsync(_scenario.Steps[i], ct);
                }
                recoveryFailures = 0;
                _resumeStepIndex = 0;
                Log?.Invoke($"===== {_cycle}판 완료 =====");
            }
            catch (RestartCycleException)
            {
                recoveryFailures = 0;
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
                            int s = Math.Clamp(_resumeStepIndex, 0, Math.Max(0, _scenario.Steps.Count - 1));
                            Log?.Invoke($"[던전 자동복구] 화면 확인 완료 -> {s + 1}. {_scenario.Steps[s].Name} 단계에서 재시작");
                        }
                        recoveryFailures = 0;
                        break;
                    }

                    Log?.Invoke($"[자동복구] {recoveryFailures}/{max} ESC 후 알고 있는 단계 화면을 확인하지 못했습니다.");
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

'''
engine = engine[:run_start] + new_run + engine[smart_start:]

# Replace smart recovery with state-aware non-Abyss recovery.
smart_start = engine.find("    private async Task<bool> TrySmartRecoveryAsync(CancellationToken ct)\n")
abyss_start = engine.find("    private async Task<bool> TryAbyssInternalRecoveryAsync(CancellationToken ct)\n")
if smart_start < 0 or abyss_start < 0 or abyss_start <= smart_start:
    raise RuntimeError("smart/abyss recovery markers missing")

new_smart = '''    private int FindDungeonStepIndex(string targetId)
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

            var retry = await _detector.DetectAsync("retry", frame, ct);
            if (retry.Found)
            {
                int step = FindDungeonStepIndex("retry");
                Log?.Invoke($"[던전 자동복구] '다시하기' 화면 확인 -> {step + 1}단계 재개");
                return step;
            }

            var touch = await _detector.DetectAsync("touch_result", frame, ct);
            if (touch.Found)
            {
                int step = FindDungeonStepIndex("touch_result");
                Log?.Invoke($"[던전 자동복구] 전투 결과/터치 화면 확인 -> {step + 1}단계 재개");
                return step;
            }

            var selected = await _detector.DetectAsync("selected", frame, ct);
            if (selected.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] '선택됨' 확인 -> 도전 상태 확인 단계({step + 1}) 재개");
                return step;
            }

            var challenge = await _detector.DetectAsync("challenge", frame, ct);
            if (challenge.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] '도전' 확인 -> {step + 1}단계 재개");
                return step;
            }

            // 입장하기만 보이는 경우에는 도전/선택됨 판정을 다시 거치도록 1단계로 보낸다.
            var enter = await _detector.DetectAsync("enter_bottom", frame, ct);
            if (enter.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] '입장하기' 화면 확인 -> 안전하게 도전 상태 확인 단계({step + 1}) 재개");
                return step;
            }

            await Task.Delay(Math.Max(300, _settings.PollIntervalMs), ct);
        }

        return null;
    }

    private async Task<bool> TrySmartRecoveryAsync(CancellationToken ct)
    {
        bool abyss = string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);
        if (abyss)
            return await TryAbyssInternalRecoveryAsync(ct);

        try
        {
            Log?.Invoke($"[던전 자동복구] 현재 {_currentStepIndex + 1}단계 실패 -> ESC 1회 입력 후 화면 재판별");
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            NativeMethods.SetForegroundWindow(_hwnd);
            _input.TapScanCode(0x01);
            await Task.Delay(800, ct);

            int? resume = await DetectKnownDungeonRecoveryStepAsync(ct);
            if (!resume.HasValue)
                return false;

            _resumeStepIndex = resume.Value;
            return true;
        }
        catch (Exception ex)
        {
            Log?.Invoke($"[던전 자동복구] 복구 판별 예외: {ex.Message}");
            return false;
        }
    }

'''
engine = engine[:smart_start] + new_smart + engine[abyss_start:]

# Replace the incorrect V0.1.21 guard with the intended invariant:
# selected -> click -> challenge stable -> allow the separate enter step.
guard_start = engine.find("    // DUNGEON_ENTRY_READY_GUARD_V3\n")
guard_end = engine.find("    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)\n")
if guard_start < 0 or guard_end < 0 or guard_end <= guard_start:
    raise RuntimeError("V0.1.21 guard block not found")

new_guard = '''    // DUNGEON_CHALLENGE_STATE_GUARD_V4
    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)
    {
        const int RequiredConsecutive = 3;
        const int ConfirmIntervalMs = 300;
        const int FinalDelayMs = 1000;
        const int MaxVerifySeconds = 45;

        int consecutive = 0;
        var verifyTimer = Stopwatch.StartNew();
        Log?.Invoke("[도전 안전확인] 규칙: 선택됨 -> 클릭 -> 도전 확인 -> 입장하기");

        while (verifyTimer.Elapsed < TimeSpan.FromSeconds(MaxVerifySeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(frame, ct))
            {
                consecutive = 0;
                continue;
            }

            var selected = await _detector.DetectAsync("selected", frame, ct);
            if (selected.Found)
            {
                Log?.Invoke($"[도전 안전확인] 선택됨 발견 -> 클릭해서 도전 상태로 변경 @ {selected.Bounds} score={selected.Score:0.000}");
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                _input.ClickClientPoint(_hwnd, selected.Center);
                consecutive = 0;
                await Task.Delay(Math.Max(600, _settings.ClickSettleMs), ct);
                continue;
            }

            var challenge = await _detector.DetectAsync("challenge", frame, ct);
            if (!challenge.Found)
            {
                consecutive = 0;
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            consecutive++;
            Log?.Invoke($"[도전 안전확인] 도전 연속 확인 {consecutive}/{RequiredConsecutive} score={challenge.Score:0.000}");
            if (consecutive < RequiredConsecutive)
            {
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            await Task.Delay(FinalDelayMs, ct);
            using var finalFrame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(finalFrame, ct))
            {
                consecutive = 0;
                continue;
            }

            var finalSelected = await _detector.DetectAsync("selected", finalFrame, ct);
            if (finalSelected.Found)
            {
                Log?.Invoke("[도전 안전확인] 최종 확인에서 선택됨 -> 다시 클릭 후 도전 재확인");
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                _input.ClickClientPoint(_hwnd, finalSelected.Center);
                consecutive = 0;
                await Task.Delay(Math.Max(600, _settings.ClickSettleMs), ct);
                continue;
            }

            var finalChallenge = await _detector.DetectAsync("challenge", finalFrame, ct);
            if (finalChallenge.Found)
            {
                Log?.Invoke("[도전 안전확인] 최종 도전 확인 성공 -> 입장하기 단계 허용");
                return;
            }

            consecutive = 0;
            Log?.Invoke("[도전 안전확인] 최종 도전 확인 실패 -> 재확인");
            await Task.Delay(ConfirmIntervalMs, ct);
        }

        throw new TimeoutException("45초 동안 선택됨 -> 도전 상태 전환을 확인하지 못했습니다.");
    }
'''
engine = engine[:guard_start] + new_guard + engine[guard_end:]

required = [
    "DUNGEON_CHALLENGE_STATE_GUARD_V4",
    "선택됨 -> 클릭 -> 도전 확인 -> 입장하기",
    "DetectKnownDungeonRecoveryStepAsync",
    "ESC 1회 입력 후 화면 재판별",
    "'다시하기' 화면 확인",
    "'선택됨' 확인 -> 도전 상태 확인 단계",
    "_resumeStepIndex",
    "selected_red_visual.png",
    "VerifyAbyssSelectionScreenAsync",
    "던전 밖 HUD 3/4 이상 확인",
]
for marker in required:
    if marker not in engine and marker != "selected_red_visual.png":
        raise RuntimeError(f"required V0.1.22 engine marker missing: {marker}")
write(engine_path, engine)

# Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.21", "V0.1.22")
                   .replace("0.1.21.0", "0.1.22.0")
                   .replace("0.1.21", "0.1.22"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.22_DUNGEON_SELECTED_STATE_RECOVERY.txt").write_text(
    "MABI AUTO V0.1.22 - DUNGEON SELECTED + STATE RECOVERY\n\n"
    "Base: V0.1.21.\n"
    "Restores the intended rule: selected -> click -> challenge confirmed -> enter.\n"
    "Adds a red selected-state visual template with OCR fallback; green/red use the same state rule.\n"
    "Dungeon Smart Recovery now presses ESC once, then recognizes known UI states and resumes from that stage.\n"
    "Known recovery states: retry, touch-result, selected, challenge, enter-bottom (safe fallback to challenge step).\n"
    "If no known state is found, the next recovery attempt presses ESC once more instead of blindly restarting from step 1.\n"
    "Abyss recovery, V0.1.20 outside HUD quorum, V0.1.19 misclick guard, and fishing behavior are preserved.\n",
    encoding="utf-8"
)

print("V0.1.22 applied: red selected hybrid + selected->challenge rule + state-aware ESC recovery")
