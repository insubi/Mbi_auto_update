#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0123_dungeon_state_resume_recovery.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

engine = read(engine_path)

# Track the failed step and the known step found after ESC.
field_marker = "    private long _lastAbyssOutsideHudScoreLog;\n"
if field_marker not in engine:
    raise RuntimeError("engine field marker missing")
engine = engine.replace(
    field_marker,
    field_marker + "    private int _currentStepIndex;\n    private int _resumeStepIndex;\n",
    1,
)

# Replace the main loop so recovery resumes at a recognized step instead of always step 1.
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
                            int s = Math.Clamp(_resumeStepIndex, 0, maxStep);
                            Log?.Invoke($"[던전 자동복구] 현재 화면 확인 완료 -> {s + 1}. {_scenario.Steps[s].Name} 단계에서 재시작");
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

'''
engine = engine[:run_start] + new_run + engine[smart_start:]

# Replace non-Abyss blind recovery with ESC -> recognize known state -> resume there.
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

            // The most specific later-stage screens are checked first.
            var retry = await _detector.DetectAsync("retry", frame, ct);
            if (retry.Found)
            {
                int step = FindDungeonStepIndex("retry");
                Log?.Invoke($"[던전 자동복구] 다시하기 확인 -> {step + 1}단계 재개");
                return step;
            }

            var touch = await _detector.DetectAsync("touch_result", frame, ct);
            if (touch.Found)
            {
                int step = FindDungeonStepIndex("touch_result");
                Log?.Invoke($"[던전 자동복구] 전투 종료/터치 화면 확인 -> {step + 1}단계 재개");
                return step;
            }

            // Selected and challenge are the same logical stage. The existing V0.1.22
            // rule will click selected and only authorize entry after challenge is confirmed.
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

            // '입장하기' can coexist with selected/challenge. If it is the only readable
            // text, go back through the challenge stage instead of entering blindly.
            var enter = await _detector.DetectAsync("enter_bottom", frame, ct);
            if (enter.Found)
            {
                int step = FindDungeonStepIndex("challenge");
                Log?.Invoke($"[던전 자동복구] 입장하기만 확인 -> 안전하게 도전 상태 확인 {step + 1}단계 재개");
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
            Log?.Invoke($"[던전 자동복구] {_currentStepIndex + 1}단계에서 오류 -> ESC 1회 입력");
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            NativeMethods.SetForegroundWindow(_hwnd);
            _input.TapScanCode(0x01); // ESC = one step back
            await Task.Delay(800, ct);

            int? resumeStep = await DetectKnownDungeonRecoveryStepAsync(ct);
            if (!resumeStep.HasValue)
            {
                Log?.Invoke("[던전 자동복구] ESC 후 8초 동안 알고 있는 단계 화면을 찾지 못함");
                return false;
            }

            _resumeStepIndex = resumeStep.Value;
            return true;
        }
        catch (Exception ex)
        {
            Log?.Invoke($"[던전 자동복구] 화면 판별 예외: {ex.Message}");
            return false;
        }
    }

'''
engine = engine[:smart_start] + new_smart + engine[abyss_start:]

required = [
    "DUNGEON_CHALLENGE_SEMANTICS_V4",
    "선택됨 확인 -> 도전 상태로 전환 위해 1회 클릭",
    "최종 도전 확인 성공 -> 입장하기 허용",
    "DetectKnownDungeonRecoveryStepAsync",
    "ESC 1회 입력",
    "다시하기 확인 ->",
    "선택됨 확인 -> 도전 상태 확인",
    "입장하기만 확인 -> 안전하게 도전 상태 확인",
    "_resumeStepIndex",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]
for marker in required:
    if marker not in engine:
        raise RuntimeError(f"required V0.1.23 marker missing: {marker}")

if "ESC 입력 후 현재 판 재시작" in engine:
    raise RuntimeError("old blind dungeon recovery still present")

write(engine_path, engine)

# Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.22", "V0.1.23")
                   .replace("0.1.22.0", "0.1.23.0")
                   .replace("0.1.22", "0.1.23"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.23_DUNGEON_STATE_RESUME_RECOVERY.txt").write_text(
    "MABI AUTO V0.1.23 - DUNGEON STATE RESUME RECOVERY\n\n"
    "Base: V0.1.22 challenge semantics.\n"
    "Keeps selected -> click -> challenge confirmed -> enter.\n"
    "Keeps the red selected visual template with OCR fallback.\n"
    "On dungeon timeout, Smart Recovery presses ESC once, waits, recognizes a known screen, and resumes from that step.\n"
    "Known screens: retry, touch-result, selected, challenge, and enter-bottom.\n"
    "Enter-bottom alone safely resumes at the challenge-state step so entry is never authorized without challenge confirmation.\n"
    "If no known screen appears, the next recovery attempt presses ESC once more and classifies again.\n"
    "Abyss Smart Recovery remains unchanged.\n",
    encoding="utf-8"
)

print("V0.1.23 applied: state-aware ESC recovery on top of V0.1.22 challenge semantics")
