#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0128_dungeon_screen_first_recovery.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
targets_path = app / "dungeon" / "config" / "targets.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


targets = json.loads(read(targets_path))

# Safety-only detections. If a policy/error shutdown screen is visible, Smart Recovery
# must not send ESC/click input. Use two independent OCR phrases for robustness.
def upsert(target):
    for i, old in enumerate(targets):
        if old.get("Id") == target["Id"]:
            targets[i] = target
            return
    targets.append(target)

upsert({
    "Id": "policy_shutdown",
    "Kind": "ocr",
    "Roi": {"X": 80, "Y": 250, "Width": 640, "Height": 500},
    "Text": "운영 정책",
    "MaxEditDistance": 2,
    "OcrRetryAt2x": True,
})
upsert({
    "Id": "policy_error88",
    "Kind": "ocr",
    "Roi": {"X": 120, "Y": 300, "Width": 560, "Height": 420},
    "Text": "ERROR 88",
    "MaxEditDistance": 2,
    "OcrRetryAt2x": True,
})
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

engine = read(engine_path)

# Replace known-screen classifier so policy shutdown is checked on every sampled frame.
detect_start = engine.find("    private async Task<int?> DetectKnownDungeonRecoveryStepAsync(CancellationToken ct)\n")
smart_start = engine.find("    private async Task<bool> TrySmartRecoveryAsync(CancellationToken ct)\n")
abyss_start = engine.find("    private async Task<bool> TryAbyssInternalRecoveryAsync(CancellationToken ct)\n")
if detect_start < 0 or smart_start < 0 or abyss_start < 0 or not (detect_start < smart_start < abyss_start):
    raise RuntimeError("dungeon recovery markers missing")

new_detect = '''    private async Task<int?> DetectKnownDungeonRecoveryStepAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();

        while (sw.Elapsed < TimeSpan.FromSeconds(8))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            // V0.1.28 safety gate: do not send recovery input on a policy shutdown screen.
            var policy = await _detector.DetectAsync("policy_shutdown", frame, ct);
            var error88 = await _detector.DetectAsync("policy_error88", frame, ct);
            if (policy.Found || error88.Found)
            {
                Log?.Invoke("[던전 자동복구] 운영 정책/ERROR 88 종료 화면 감지 -> 모든 복구 입력 중지");
                throw new InvalidOperationException("DUNGEON_POLICY_SHUTDOWN_DETECTED");
            }

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

'''

new_smart = '''    // DUNGEON_SCREEN_FIRST_RECOVERY_V6
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
        catch (InvalidOperationException ex) when (ex.Message == "DUNGEON_POLICY_SHUTDOWN_DETECTED")
        {
            // Intentionally escape Smart Recovery. RunAsync does not swallow this exception,
            // so the dungeon automation stops instead of sending more game input.
            throw;
        }
        catch (Exception ex)
        {
            Log?.Invoke($"[던전 자동복구] 화면 우선 판별 예외: {ex.Message}");
            return false;
        }
    }

'''

engine = engine[:detect_start] + new_detect + new_smart + engine[abyss_start:]

required_markers = [
    "DUNGEON_SCREEN_FIRST_RECOVERY_V6",
    "ESC 없이 현재 화면 먼저 판별",
    "최후 수단 ESC 1회 입력 후 재판별",
    "추가 ESC 없음",
    "DUNGEON_POLICY_SHUTDOWN_DETECTED",
    "DUNGEON_CHALLENGE_DISAMBIGUATION_V5",
    "DUNGEON_UPDATE_20260917_MENU_FALLBACK",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]
# V0.1.27 menu-fallback marker must be gone because the old blind second-ESC logic is replaced.
for marker in required_markers[:-3]:
    if marker not in engine:
        raise RuntimeError(f"required V0.1.28 marker missing: {marker}")
if "DUNGEON_UPDATE_20260917_MENU_FALLBACK" in engine:
    raise RuntimeError("old V0.1.27 blind second-ESC fallback still present")
for marker in required_markers[-2:]:
    if marker not in engine:
        raise RuntimeError(f"preserved marker missing: {marker}")

write(engine_path, engine)

# Runtime version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.27", "V0.1.28")
                   .replace("0.1.27.0", "0.1.28.0")
                   .replace("0.1.27", "0.1.28"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.28_DUNGEON_SCREEN_FIRST_RECOVERY.txt").write_text(
    "MABI AUTO V0.1.28 - DUNGEON SCREEN-FIRST RECOVERY\n\n"
    "Base: V0.1.27 2026-09-17 dungeon UI compatibility.\n"
    "Smart Recovery now classifies the current screen before sending ESC.\n"
    "Known screens resume directly: retry, touch-result, selected, challenge, enter-bottom.\n"
    "Only when no known state is found for 8 seconds is one ESC sent, followed by one more classification pass.\n"
    "No blind second ESC is sent within the same recovery attempt. Outer recovery-attempt limits still provide safe-stop behavior.\n"
    "Policy shutdown / ERROR 88 OCR gates stop recovery input immediately.\n"
    "V0.1.27 purple entry UI/retry OCR, V0.1.26 scene-skip monitor, Abyss recovery, and fishing behavior are preserved.\n",
    encoding="utf-8"
)

print("V0.1.28 applied: screen-first dungeon recovery with policy shutdown safety gate")
