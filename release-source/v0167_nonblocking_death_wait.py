#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
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

# ---------------------------------------------------------------------------
# 1) V0.1.66 used a blocking 5-minute Task.Delay inside CheckMonitorsAsync.
# That froze the current Abyss step, so a party clear during the death wait
# could not reach the normal clear/touch/result logic.
#
# V0.1.67 turns this into a non-blocking deadline:
#   death 2/2 -> schedule + keep scanning
#   clear/result during wait -> cancel pending exit and let normal step handle it
#   deadline -> fresh death 2/2 -> leave, otherwise cancel
# ---------------------------------------------------------------------------
check_sig = "    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)\n    {\n"
if engine.count(check_sig) != 1:
    raise SystemExit("CheckMonitorsAsync signature mismatch")

pending_guard = r'''    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)
    {
        // V0167_ABYSS_DEATH_WAIT_NONBLOCKING
        // A death-confirmed character may wait up to 5 minutes for the party to clear.
        // This is a deadline, NOT a blocking delay, so normal clear/result processing keeps running.
        const string AbyssDeathPendingKey = "__abyss_death_exit_pending_until";
        bool abyssPendingRuntime =
            string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);

        if (abyssPendingRuntime &&
            _monitorLastScan.TryGetValue(AbyssDeathPendingKey, out long deathExitPendingUntil))
        {
            // Clear/result always wins over the delayed death exit.
            // Return false so the caller's normal step logic handles the detected screen now.
            var clearDuringDeathWait = await DetectAbyssConfirmedClearAsync(frame, ct);
            if (clearDuringDeathWait.Found)
            {
                _monitorLastScan.Remove(AbyssDeathPendingKey);
                Log?.Invoke("[어비스 사망] 5분 대기 중 클리어 화면 확인 -> 퇴장 예약 취소, 클리어 처리 우선");
                return false;
            }

            var resultDuringDeathWait = await DetectAbyssResultRetryAsync(frame, ct);
            if (resultDuringDeathWait.Found)
            {
                _monitorLastScan.Remove(AbyssDeathPendingKey);
                Log?.Invoke("[어비스 사망] 5분 대기 중 결과/다시 하기 화면 확인 -> 퇴장 예약 취소, 결과 처리 우선");
                return false;
            }

            if (Environment.TickCount64 >= deathExitPendingUntil)
            {
                // Five minutes elapsed. Reconfirm death on two fresh frames before leaving.
                var deathAfter1 = await _detector.DetectAsync("abyss_death_state", frame, ct);
                var reviveAfter1 = await _detector.DetectAsync("abyss_revive_here", frame, ct);
                var visualAfter1 = DetectAbyssDeathVisualState(frame);
                bool stillDeath1 = (deathAfter1.Found || visualAfter1.Death) &&
                                   (reviveAfter1.Found || visualAfter1.Revive);

                if (!stillDeath1)
                {
                    _monitorLastScan.Remove(AbyssDeathPendingKey);
                    Log?.Invoke("[어비스 사망] 5분 만료 후 사망 상태 해제 -> 던전 퇴장 취소, 현재 진행 계속");
                    return false;
                }

                Log?.Invoke($"[어비스 사망] 5분 만료 후 사망 상태 재확인 1/2 (visual red={visualAfter1.RedRatio:0.000}, orange={visualAfter1.OrangeRatio:0.000})");
                await Task.Delay(250, ct);

                using var deathAfterFrame2 = await CaptureGameWindowAsync(ct);

                // The screen may transition to clear/result during the 250ms recheck too.
                var clearAfter2 = await DetectAbyssConfirmedClearAsync(deathAfterFrame2, ct);
                if (clearAfter2.Found)
                {
                    _monitorLastScan.Remove(AbyssDeathPendingKey);
                    Log?.Invoke("[어비스 사망] 5분 만료 재확인 중 클리어 화면 전환 -> 퇴장 취소, 클리어 처리 우선");
                    return false;
                }

                var resultAfter2 = await DetectAbyssResultRetryAsync(deathAfterFrame2, ct);
                if (resultAfter2.Found)
                {
                    _monitorLastScan.Remove(AbyssDeathPendingKey);
                    Log?.Invoke("[어비스 사망] 5분 만료 재확인 중 결과 화면 전환 -> 퇴장 취소, 결과 처리 우선");
                    return false;
                }

                var deathAfter2 = await _detector.DetectAsync("abyss_death_state", deathAfterFrame2, ct);
                var reviveAfter2 = await _detector.DetectAsync("abyss_revive_here", deathAfterFrame2, ct);
                var visualAfter2 = DetectAbyssDeathVisualState(deathAfterFrame2);
                bool stillDeath2 = (deathAfter2.Found || visualAfter2.Death) &&
                                   (reviveAfter2.Found || visualAfter2.Revive);

                if (!stillDeath2)
                {
                    _monitorLastScan.Remove(AbyssDeathPendingKey);
                    Log?.Invoke("[어비스 사망] 5분 만료 후 사망 상태 2/2 불일치 -> 던전 퇴장 취소, 현재 진행 계속");
                    return false;
                }

                _monitorLastScan.Remove(AbyssDeathPendingKey);
                Log?.Invoke($"[어비스 사망] 5분 만료 후 사망 상태 2/2 유지 -> 던전 퇴장 시작 (visual red={visualAfter2.RedRatio:0.000}, orange={visualAfter2.OrangeRatio:0.000})");
                await HandleAbyssDeathExitAsync(ct);
                throw new RestartCycleException();
            }
        }

'''
engine = engine.replace(check_sig, pending_guard, 1)

# Replace the full V0.1.66 death-monitor block up to scene_skip.
death_start_marker = '            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))\n'
scene_start_marker = '            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))\n'
death_start = engine.find(death_start_marker)
scene_start = engine.find(scene_start_marker, death_start + 1)
if death_start < 0 or scene_start < 0 or scene_start <= death_start:
    raise SystemExit("death/scene monitor block boundary mismatch")

new_death_block = r'''            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
            {
                // Already confirmed and counting down: do not restart the 5-minute timer.
                if (_monitorLastScan.ContainsKey(AbyssDeathPendingKey))
                    continue;

                var revive = await _detector.DetectAsync("abyss_revive_here", frame, ct);
                var visual1 = DetectAbyssDeathVisualState(frame);
                bool death1 = r.Found || visual1.Death;
                bool revive1 = revive.Found || visual1.Revive;
                if (!death1 || !revive1)
                    continue;

                Log?.Invoke($"[어비스 사망] 행동불능 + 여기서 부활 후보 1/2 -> 별도 프레임 재확인 (visual red={visual1.RedRatio:0.000}, orange={visual1.OrangeRatio:0.000})");
                await Task.Delay(250, ct);

                using var deathConfirmFrame = await CaptureGameWindowAsync(ct);
                var deathConfirm = await _detector.DetectAsync("abyss_death_state", deathConfirmFrame, ct);
                var reviveConfirm = await _detector.DetectAsync("abyss_revive_here", deathConfirmFrame, ct);
                var visual2 = DetectAbyssDeathVisualState(deathConfirmFrame);
                bool death2 = deathConfirm.Found || visual2.Death;
                bool revive2 = reviveConfirm.Found || visual2.Revive;

                if (!death2 || !revive2)
                {
                    Log?.Invoke("[어비스 사망] 2차 확인 실패 -> 아무 입력도 하지 않음");
                    continue;
                }

                _monitorLastAction[m.Target] = Environment.TickCount64;
                _monitorLastScan[AbyssDeathPendingKey] =
                    Environment.TickCount64 + (long)TimeSpan.FromMinutes(5).TotalMilliseconds;

                Log?.Invoke($"[어비스 사망] 행동불능 + 여기서 부활 2/2 확인 -> 5분 퇴장 타이머 시작, 화면 감시 계속 (visual red={visual2.RedRatio:0.000}, orange={visual2.OrangeRatio:0.000})");
                continue;
            }

'''
engine = engine[:death_start] + new_death_block + engine[scene_start:]

# The blocking 5-minute wait must be completely gone.
if "await Task.Delay(TimeSpan.FromMinutes(5), ct);" in engine:
    raise SystemExit("blocking 5-minute death delay still present")

write(engine_path, engine)

# ---------------------------------------------------------------------------
# 2) Version metadata.
# ---------------------------------------------------------------------------
project = read(project_path)
for old, new in (
    ("<Version>0.1.66</Version>", "<Version>0.1.67</Version>"),
    ("<AssemblyVersion>0.1.66.0</AssemblyVersion>", "<AssemblyVersion>0.1.67.0</AssemblyVersion>"),
    ("<FileVersion>0.1.66.0</FileVersion>", "<FileVersion>0.1.67.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.66"' not in update:
    raise SystemExit("UpdateManager V0.1.66 marker missing")
update = update.replace('CurrentVersion = "V0.1.66"', 'CurrentVersion = "V0.1.67"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 3) Static invariants.
# ---------------------------------------------------------------------------
patched = read(engine_path)
for marker in (
    "V0167_ABYSS_DEATH_WAIT_NONBLOCKING",
    "__abyss_death_exit_pending_until",
    "5분 퇴장 타이머 시작, 화면 감시 계속",
    "5분 대기 중 클리어 화면 확인 -> 퇴장 예약 취소, 클리어 처리 우선",
    "5분 대기 중 결과/다시 하기 화면 확인 -> 퇴장 예약 취소, 결과 처리 우선",
    "5분 만료 후 사망 상태 재확인 1/2",
    "5분 만료 후 사망 상태 2/2 유지 -> 던전 퇴장 시작",
    "V0166_ABYSS_SCENE_SKIP_OUTLINE",
    "death-visual-pair",
    "scene_skip 보류 -> 사망 화면 우선",
    "V0164_ABYSS_CLEAR_LOG_SIMPLIFIED",
    "실제 결과 화면 후보 1/2",
    "실제 결과 화면 2/2 확인",
    "회복 물약 팝업 ESC 후 닫힘 2프레임 확인",
):
    if marker not in patched:
        raise SystemExit(f"required runtime marker missing: {marker}")

if "Task.Delay(TimeSpan.FromMinutes(5), ct)" in patched:
    raise SystemExit("blocking 5-minute delay survived V0.1.67")

allowed = {
    engine_path.relative_to(root).as_posix(),
    project_path.relative_to(root).as_posix(),
    update_path.relative_to(root).as_posix(),
}
after_tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                 {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
after = {p.relative_to(root).as_posix(): digest(p) for p in after_tracked}
changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
unexpected = sorted(changed - allowed)
if unexpected:
    raise SystemExit("unexpected runtime/source changes: " + ", ".join(unexpected))

print("V0.1.67 applied: non-blocking 5-minute death deadline with clear/result priority")
