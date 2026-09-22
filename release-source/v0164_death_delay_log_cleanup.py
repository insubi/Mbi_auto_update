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

# 1) Simplify the noisy clear-candidate diagnostic log only.
# Detection thresholds and state transitions are intentionally untouched.
old_score_log = '''        if (clearTitle.Score > 0 || touch.Score > 0)
            Log?.Invoke($"[어비스] 클리어 후보 점수: title={clearTitle.Score:0.000}, touch={touch.Score:0.000}");
'''
new_score_log = '''        // V0164_ABYSS_CLEAR_LOG_SIMPLIFIED:
        // Suppress ordinary combat similarity noise. This affects logging only.
        const double ClearCandidateLogThreshold = 0.65;
        if (clearTitle.Score >= ClearCandidateLogThreshold || touch.Score >= ClearCandidateLogThreshold)
            Log?.Invoke($"[어비스] 강한 클리어 후보: title={clearTitle.Score:0.000}, touch={touch.Score:0.000}");
'''
if engine.count(old_score_log) != 1:
    raise SystemExit("clear candidate score-log anchor mismatch")
engine = engine.replace(old_score_log, new_score_log, 1)

# 2) After death has been confirmed on 2 separate frames, wait exactly 5 minutes
# before beginning the existing no-revive dungeon-exit flow.
old_death = '''                _monitorLastAction[m.Target] = Environment.TickCount64;
                Log?.Invoke("[어비스 사망] 행동불능 + 여기서 부활 2/2 확인 -> 부활하지 않고 퇴장");
                await HandleAbyssDeathExitAsync(ct);
                throw new RestartCycleException();
'''
new_death = '''                _monitorLastAction[m.Target] = Environment.TickCount64;
                // V0164_ABYSS_DEATH_EXIT_DELAY_5_MINUTES:
                // Death is already confirmed 2/2. Do not revive or send other game input
                // during this wait. F10/cancellation still interrupts the delay immediately.
                Log?.Invoke("[어비스 사망] 행동불능 + 여기서 부활 2/2 확인 -> 5분 대기 후 퇴장");
                await Task.Delay(TimeSpan.FromMinutes(5), ct);
                Log?.Invoke("[어비스 사망] 5분 대기 완료 -> 던전 퇴장 시작");
                await HandleAbyssDeathExitAsync(ct);
                throw new RestartCycleException();
'''
if engine.count(old_death) != 1:
    raise SystemExit("Abyss death 2/2 exit anchor mismatch")
engine = engine.replace(old_death, new_death, 1)
write(engine_path, engine)

# 3) Version metadata.
project = read(project_path)
for old, new in (
    ("<Version>0.1.63</Version>", "<Version>0.1.64</Version>"),
    ("<AssemblyVersion>0.1.63.0</AssemblyVersion>", "<AssemblyVersion>0.1.64.0</AssemblyVersion>"),
    ("<FileVersion>0.1.63.0</FileVersion>", "<FileVersion>0.1.64.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.63"' not in update:
    raise SystemExit("UpdateManager V0.1.63 marker missing")
update = update.replace('CurrentVersion = "V0.1.63"', 'CurrentVersion = "V0.1.64"', 1)
write(update_path, update)

# Static verification.
patched = read(engine_path)
for marker in (
    "V0164_ABYSS_CLEAR_LOG_SIMPLIFIED",
    "ClearCandidateLogThreshold = 0.65",
    "[어비스] 강한 클리어 후보:",
    "V0164_ABYSS_DEATH_EXIT_DELAY_5_MINUTES",
    "Task.Delay(TimeSpan.FromMinutes(5), ct)",
    "5분 대기 완료 -> 던전 퇴장 시작",
    "부활 사용 안 함 -> 던전 퇴장 절차 시작",
    "행동불능 + 여기서 부활 후보 1/2",
    "scene_skip 2/2 연속 확인",
    "실제 결과 화면 후보 1/2",
    "실제 결과 화면 2/2 확인",
    "회복 물약 팝업 ESC 후 닫힘 2프레임 확인",
):
    if marker not in patched:
        raise SystemExit(f"required runtime marker missing: {marker}")

if "클리어 후보 점수:" in patched:
    raise SystemExit("old noisy clear-candidate log still present")
if "행동불능 + 여기서 부활 2/2 확인 -> 부활하지 않고 퇴장" in patched:
    raise SystemExit("old immediate death-exit path still present")

# Restrict this patch to ScenarioEngine + version metadata only.
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

if "<Version>0.1.64</Version>" not in read(project_path):
    raise SystemExit("project version not V0.1.64")
if 'CurrentVersion = "V0.1.64"' not in read(update_path):
    raise SystemExit("updater version not V0.1.64")

print("V0.1.64 applied: 5-minute delayed death exit + simplified Abyss clear-candidate logging")
