#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import shutil
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0129_full_stability_hardening.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
dungeon_targets_path = app / "dungeon" / "config" / "targets.json"
abyss_targets_path = app / "abyss" / "config" / "targets.json"
retry_asset = Path(__file__).resolve().parent / "assets" / "retry_visual_v0129.jpg"
retry_template = app / "dungeon" / "templates" / "retry_visual_v0129.jpg"

EXPECTED_RETRY_SHA256 = "0089b636041b76b4eabd269b7c50b82d045ef11f66368797947b7f72adea59aa"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def upsert(items, target):
    for i, old in enumerate(items):
        if str(old.get("Id", "")).lower() == str(target["Id"]).lower():
            items[i] = target
            return
    items.append(target)


def policy_targets():
    return [
        {
            "Id": "policy_shutdown",
            "Kind": "ocr",
            "Roi": {"X": 80, "Y": 250, "Width": 640, "Height": 500},
            "Text": "운영 정책",
            "MaxEditDistance": 2,
            "OcrRetryAt2x": True,
        },
        {
            "Id": "policy_error88",
            "Kind": "ocr",
            "Roi": {"X": 120, "Y": 300, "Width": 560, "Height": 420},
            "Text": "ERROR 88",
            "MaxEditDistance": 2,
            "OcrRetryAt2x": True,
        },
    ]


# 1) Retry: preserve OCR and add the user-provided updated green button as visual fallback.
if not retry_asset.exists():
    raise RuntimeError(f"retry visual asset missing: {retry_asset}")
asset_hash = hashlib.sha256(retry_asset.read_bytes()).hexdigest()
if asset_hash != EXPECTED_RETRY_SHA256:
    raise RuntimeError(f"retry visual asset hash mismatch: {asset_hash}")
retry_template.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(retry_asset, retry_template)

targets = json.loads(read(dungeon_targets_path))
by_id = {str(t.get("Id", "")): t for t in targets}
if "retry" not in by_id:
    raise RuntimeError("retry target missing")
retry = by_id["retry"]
retry.update({
    "Kind": "hybrid",
    "Roi": {"X": 180, "Y": 830, "Width": 440, "Height": 170},
    "Text": "다시 하기",
    "MaxEditDistance": 2,
    "OcrRetryAt2x": True,
    "TemplatePath": "templates/retry_visual_v0129.jpg",
    "Threshold": 0.70,
    "TemplateScaleMin": 0.50,
    "TemplateScaleMax": 1.30,
    "TemplateScaleStep": 0.05,
})
for t in policy_targets():
    upsert(targets, t)
write(dungeon_targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# ERROR 88 / policy shutdown is a game-global condition, so Abyss gets the same safety targets.
if abyss_targets_path.exists():
    abyss_targets = json.loads(read(abyss_targets_path))
    for t in policy_targets():
        upsert(abyss_targets, t)
    write(abyss_targets_path, json.dumps(abyss_targets, ensure_ascii=False, indent=2) + "\n")

engine = read(engine_path)

# 2) Same-stage recovery loop guard. A successful screen classification must not reset
# the protection forever; repeated returns to the same recovery stage are counted.
old_init = "        int recoveryFailures = 0;\n"
new_init = """        int recoveryFailures = 0;
        int repeatedRecoveryStep = -1;
        int repeatedRecoveryCount = 0;
"""
if old_init not in engine:
    raise RuntimeError("RunAsync recovery counter init not found")
engine = engine.replace(old_init, new_init, 1)

old_complete = """                recoveryFailures = 0;
                _resumeStepIndex = 0;
                Log?.Invoke($"===== {_cycle}판 완료 =====");
"""
new_complete = """                recoveryFailures = 0;
                repeatedRecoveryStep = -1;
                repeatedRecoveryCount = 0;
                _resumeStepIndex = 0;
                Log?.Invoke($"===== {_cycle}판 완료 =====");
"""
if old_complete not in engine:
    raise RuntimeError("normal cycle recovery reset block not found")
engine = engine.replace(old_complete, new_complete, 1)

old_restart = """                recoveryFailures = 0;
                _resumeStepIndex = 0;
                Log?.Invoke("감시 항목에 의해 현재 판을 처음부터 다시 시작합니다.");
"""
new_restart = """                recoveryFailures = 0;
                repeatedRecoveryStep = -1;
                repeatedRecoveryCount = 0;
                _resumeStepIndex = 0;
                Log?.Invoke("감시 항목에 의해 현재 판을 처음부터 다시 시작합니다.");
"""
if old_restart not in engine:
    raise RuntimeError("RestartCycle recovery reset block not found")
engine = engine.replace(old_restart, new_restart, 1)

old_recovered = """                    if (recovered)
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
"""
new_recovered = """                    if (recovered)
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
"""
if old_recovered not in engine:
    raise RuntimeError("successful recovery block not found")
engine = engine.replace(old_recovered, new_recovered, 1)

# 3) Policy/ERROR 88 must propagate out of Smart Recovery and reach MainForm's existing
# generic error/Telegram alert path with a human-readable message.
engine = engine.replace(
    'throw new InvalidOperationException("DUNGEON_POLICY_SHUTDOWN_DETECTED");',
    'throw new InvalidOperationException("DUNGEON_POLICY_SHUTDOWN_DETECTED: 운영 정책/ERROR 88 화면 감지 -> 자동 입력 즉시 정지");'
)
old_filter = 'catch (InvalidOperationException ex) when (ex.Message == "DUNGEON_POLICY_SHUTDOWN_DETECTED")'
new_filter = 'catch (InvalidOperationException ex) when (ex.Message.StartsWith("DUNGEON_POLICY_SHUTDOWN_DETECTED", StringComparison.Ordinal))'
if old_filter not in engine:
    raise RuntimeError("policy shutdown Smart Recovery catch filter not found")
engine = engine.replace(old_filter, new_filter, 1)

# Put the policy guard before every monitor action. It is throttled to 650ms so OCR
# remains responsive without doing two large OCR scans on every 300ms game frame.
monitor_sig = "    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)\n    {\n"
if monitor_sig not in engine:
    raise RuntimeError("CheckMonitorsAsync signature not found")
policy_helper = """    // DUNGEON_GLOBAL_POLICY_GUARD_V7
    private async Task ThrowIfDungeonPolicyShutdownAsync(Bitmap frame, CancellationToken ct)
    {
        const string guardKey = "__policy_shutdown_guard";
        long now = Environment.TickCount64;
        if (_monitorLastScan.TryGetValue(guardKey, out var last) && now - last < 650)
            return;
        _monitorLastScan[guardKey] = now;

        var policy = await _detector.DetectAsync("policy_shutdown", frame, ct);
        var error88 = await _detector.DetectAsync("policy_error88", frame, ct);
        if (!policy.Found && !error88.Found)
            return;

        Log?.Invoke("[전역 안전감지] 운영 정책/ERROR 88 화면 감지 -> 장면넘기기/자동복구/자동클릭 포함 모든 입력 즉시 정지");
        throw new InvalidOperationException("DUNGEON_POLICY_SHUTDOWN_DETECTED: 운영 정책/ERROR 88 화면 감지 -> 자동 입력 즉시 정지");
    }

    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)
    {
        await ThrowIfDungeonPolicyShutdownAsync(frame, ct);
"""
engine = engine.replace(monitor_sig, policy_helper, 1)

# 4) Scene skip: one positive frame is no longer enough to click. Capture a second,
# separate frame and require the same target again. Policy guard wins on confirmation too.
old_monitor_detect = """            var r = await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            _monitorLastAction[m.Target] = Environment.TickCount64;
"""
new_monitor_detect = """            var r = await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
            {
                Log?.Invoke($"[monitor] scene_skip 1/2 확인 ({r.ReadText ?? r.Score.ToString("0.000")}) -> 별도 프레임 재확인");
                await Task.Delay(220, ct);
                using var confirmFrame = await CaptureGameWindowAsync(ct);
                await ThrowIfDungeonPolicyShutdownAsync(confirmFrame, ct);
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
"""
if old_monitor_detect not in engine:
    raise RuntimeError("monitor detect/action block not found")
engine = engine.replace(old_monitor_detect, new_monitor_detect, 1)

# Marker for build-time verification.
marker_anchor = "    // HANDLE_RECOVERY_V2\n"
if marker_anchor not in engine:
    raise RuntimeError("HANDLE_RECOVERY_V2 marker missing")
engine = engine.replace(marker_anchor, "    // DUNGEON_FULL_STABILITY_HARDENING_V7\n" + marker_anchor, 1)

required_markers = [
    "DUNGEON_FULL_STABILITY_HARDENING_V7",
    "DUNGEON_GLOBAL_POLICY_GUARD_V7",
    "동일 단계 복구",
    "같은 복구 단계가",
    "scene_skip 1/2 확인",
    "scene_skip 2/2 연속 확인",
    "DUNGEON_SCREEN_FIRST_RECOVERY_V6",
    "DUNGEON_CHALLENGE_DISAMBIGUATION_V5",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]
for marker in required_markers:
    if marker not in engine:
        raise RuntimeError(f"required marker missing after V0.1.29 patch: {marker}")
write(engine_path, engine)

# Runtime version bump only.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.28", "V0.1.29")
                   .replace("0.1.28.0", "0.1.29.0")
                   .replace("0.1.28", "0.1.29"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.29_FULL_STABILITY_HARDENING.txt").write_text(
    "MABI AUTO V0.1.29 - FULL STABILITY HARDENING\n\n"
    "Base: V0.1.28 screen-first recovery.\n"
    "Retry detection is now hybrid OCR + the updated green '다시 하기' visual template.\n"
    "Repeated successful recovery to the same dungeon stage is counted; reaching AutoRecoveryMaxAttempts safely stops instead of looping forever.\n"
    "Policy shutdown / ERROR 88 OCR is now checked before monitor actions in the normal dungeon/Abyss monitor path and propagates to the existing Telegram error alert path.\n"
    "Scene-skip requires two detections on separate frames before clicking.\n"
    "V0.1.27 purple selected/challenge entry handling, V0.1.28 screen-first recovery, Abyss recovery, fishing logic, F10 stop, logging and notifications are preserved.\n",
    encoding="utf-8"
)

print("V0.1.29 applied: retry visual fallback + recovery loop guard + global policy guard + two-frame scene skip")
