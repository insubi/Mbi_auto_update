#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
targets_path = app / "abyss" / "config" / "targets.json"
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

# ---------------------------------------------------------------------------
# 1) Scene skip: image-only + tighter top-right ROI.
# The previous hybrid detector could accept OCR alone on the normal HUD.
# Keep the existing scene-skip template but remove OCR as an authorization path.
# ---------------------------------------------------------------------------
targets = json.loads(read(targets_path))
scene = next((t for t in targets if t.get("Id") == "scene_skip"), None)
if scene is None:
    raise SystemExit("scene_skip target missing")
if not scene.get("TemplatePath"):
    raise SystemExit("scene_skip existing template missing")

scene["Kind"] = "template"
scene["Roi"] = {"X": 620, "Y": 20, "Width": 180, "Height": 90}
scene["Threshold"] = 0.74
scene["TemplateScaleMin"] = 0.80
scene["TemplateScaleMax"] = 1.25
scene["TemplateScaleStep"] = 0.04
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# ---------------------------------------------------------------------------
# 2) Runtime death visual fallback from the recorded real death screen.
# OCR remains available, but fixed 800x1000 red/orange UI color evidence can
# independently confirm the two required death signals.
# ---------------------------------------------------------------------------
engine = read(engine_path)

helper_anchor = "    // V0162_ABYSS_DEATH_EXIT_NO_REVIVE\n"
if helper_anchor not in engine:
    raise SystemExit("death helper anchor missing")

visual_helper = r'''    // V0165_ABYSS_DEATH_VISUAL_FALLBACK
    // Recorded 800x1000 death UI:
    //   red "행동불능" around x=300..499, y=130..259
    //   orange "여기서 부활" button around x=220..439, y=780..879
    // Sample every 2 pixels to keep the monitor cheap. Both regions must agree.
    private static (bool Death, bool Revive, double RedRatio, double OrangeRatio)
        DetectAbyssDeathVisualState(Bitmap frame)
    {
        if (frame.Width != 800 || frame.Height != 1000)
            return (false, false, 0.0, 0.0);

        int redHits = 0, redTotal = 0;
        for (int y = 130; y < 260; y += 2)
        {
            for (int x = 300; x < 500; x += 2)
            {
                var c = frame.GetPixel(x, y);
                redTotal++;
                if (c.R >= 170 && c.G <= 150 &&
                    c.R - c.G >= 45 && c.R - c.B >= 55)
                    redHits++;
            }
        }

        int orangeHits = 0, orangeTotal = 0;
        for (int y = 780; y < 880; y += 2)
        {
            for (int x = 220; x < 440; x += 2)
            {
                var c = frame.GetPixel(x, y);
                orangeTotal++;
                if (c.R >= 180 && c.G >= 75 && c.G <= 210 && c.B <= 140 &&
                    c.R - c.G >= 35)
                    orangeHits++;
            }
        }

        double redRatio = redTotal == 0 ? 0.0 : (double)redHits / redTotal;
        double orangeRatio = orangeTotal == 0 ? 0.0 : (double)orangeHits / orangeTotal;

        // Recorded stable death frames were ~0.065 red and ~0.245 orange.
        // Non-death samples stayed below ~0.040 red and ~0.071 orange.
        return (redRatio >= 0.050, orangeRatio >= 0.160, redRatio, orangeRatio);
    }

'''
engine = engine.replace(helper_anchor, visual_helper + helper_anchor, 1)

# Replace the V0.1.64 death monitor block.
old_death = '''            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
            {
                var revive = await _detector.DetectAsync("abyss_revive_here", frame, ct);
                if (!revive.Found)
                    continue;

                Log?.Invoke("[어비스 사망] 행동불능 + 여기서 부활 후보 1/2 -> 별도 프레임 재확인");
                await Task.Delay(250, ct);

                using var deathConfirmFrame = await CaptureGameWindowAsync(ct);
                var deathConfirm = await _detector.DetectAsync("abyss_death_state", deathConfirmFrame, ct);
                var reviveConfirm = await _detector.DetectAsync("abyss_revive_here", deathConfirmFrame, ct);

                if (!deathConfirm.Found || !reviveConfirm.Found)
                {
                    Log?.Invoke("[어비스 사망] 2차 확인 실패 -> 아무 입력도 하지 않음");
                    continue;
                }

                _monitorLastAction[m.Target] = Environment.TickCount64;
                // V0164_ABYSS_DEATH_EXIT_DELAY_5_MINUTES:
                // Death is already confirmed 2/2. Do not revive or send other game input
                // during this wait. F10/cancellation still interrupts the delay immediately.
                Log?.Invoke("[어비스 사망] 행동불능 + 여기서 부활 2/2 확인 -> 5분 대기 후 퇴장");
                await Task.Delay(TimeSpan.FromMinutes(5), ct);
                Log?.Invoke("[어비스 사망] 5분 대기 완료 -> 던전 퇴장 시작");
                await HandleAbyssDeathExitAsync(ct);
                throw new RestartCycleException();
            }
'''
new_death = '''            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
            {
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
                Log?.Invoke($"[어비스 사망] 행동불능 + 여기서 부활 2/2 확인 -> 5분 대기 (visual red={visual2.RedRatio:0.000}, orange={visual2.OrangeRatio:0.000})");
                await Task.Delay(TimeSpan.FromMinutes(5), ct);

                // V0165_ABYSS_DEATH_POSTWAIT_RECHECK
                // Five minutes later, do not blindly leave. The party may have cleared the
                // dungeon while this character was down. Re-check the current screen first.
                using var postWaitFrame = await CaptureGameWindowAsync(ct);
                var deathAfter = await _detector.DetectAsync("abyss_death_state", postWaitFrame, ct);
                var reviveAfter = await _detector.DetectAsync("abyss_revive_here", postWaitFrame, ct);
                var visualAfter = DetectAbyssDeathVisualState(postWaitFrame);
                bool stillDeath = (deathAfter.Found || visualAfter.Death) &&
                                  (reviveAfter.Found || visualAfter.Revive);

                if (!stillDeath)
                {
                    var clearAfter = await DetectAbyssConfirmedClearAsync(postWaitFrame, ct);
                    var resultAfter = await DetectAbyssResultRetryAsync(postWaitFrame, ct);
                    string state = clearAfter.Found
                        ? "클리어 화면"
                        : resultAfter.Found
                            ? "결과/다시 하기 화면"
                            : "사망 화면 해제";

                    Log?.Invoke($"[어비스 사망] 5분 후 재확인: {state} -> 던전 퇴장 취소, 현재 단계 정상 진행 재개");
                    return true;
                }

                Log?.Invoke($"[어비스 사망] 5분 후에도 사망 화면 유지 -> 던전 퇴장 시작 (visual red={visualAfter.RedRatio:0.000}, orange={visualAfter.OrangeRatio:0.000})");
                await HandleAbyssDeathExitAsync(ct);
                throw new RestartCycleException();
            }
'''
if engine.count(old_death) != 1:
    raise SystemExit("V0.1.64 death monitor block mismatch")
engine = engine.replace(old_death, new_death, 1)

# ---------------------------------------------------------------------------
# 3) Scene-skip safety: death state always wins over scene-skip.
# Template-only detection is already enforced in targets.json; additionally
# block the click on both the first and confirmation frames if death UI exists.
# ---------------------------------------------------------------------------
scene_start = engine.find('            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))\n')
scene_end = engine.find("            _monitorLastAction[m.Target] = Environment.TickCount64;\n", scene_start)
if scene_start < 0 or scene_end < 0 or scene_end <= scene_start:
    raise SystemExit("scene_skip runtime block boundary mismatch")

new_scene = '''            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
            {
                var sceneDeath1 = DetectAbyssDeathVisualState(frame);
                var sceneDeathOcr1 = await _detector.DetectAsync("abyss_death_state", frame, ct);
                var sceneRevive1 = await _detector.DetectAsync("abyss_revive_here", frame, ct);
                if ((sceneDeathOcr1.Found || sceneDeath1.Death) &&
                    (sceneRevive1.Found || sceneDeath1.Revive))
                {
                    Log?.Invoke("[monitor] scene_skip 보류 -> 사망 화면 우선");
                    continue;
                }

                Log?.Invoke($"[monitor] scene_skip 1/2 이미지 확인 ({r.Score:0.000}) -> 별도 프레임 재확인");
                await Task.Delay(220, ct);
                using var confirmFrame = await CaptureGameWindowAsync(ct);

                var sceneDeath2 = DetectAbyssDeathVisualState(confirmFrame);
                var sceneDeathOcr2 = await _detector.DetectAsync("abyss_death_state", confirmFrame, ct);
                var sceneRevive2 = await _detector.DetectAsync("abyss_revive_here", confirmFrame, ct);
                if ((sceneDeathOcr2.Found || sceneDeath2.Death) &&
                    (sceneRevive2.Found || sceneDeath2.Revive))
                {
                    Log?.Invoke("[monitor] scene_skip 2차 확인 중 사망 화면 확인 -> 클릭 취소");
                    continue;
                }

                var confirm = await _detector.DetectAsync(m.Target, confirmFrame, ct);
                if (!confirm.Found)
                {
                    Log?.Invoke("[monitor] scene_skip 2차 이미지 확인 실패 -> 클릭 취소");
                    continue;
                }
                r = confirm;
                Log?.Invoke($"[monitor] scene_skip 2/2 이미지 연속 확인 -> 클릭 허용 ({r.Score:0.000})");
            }

'''
engine = engine[:scene_start] + new_scene + engine[scene_end:]

write(engine_path, engine)

# ---------------------------------------------------------------------------
# 4) Version metadata.
# ---------------------------------------------------------------------------
project = read(project_path)
for old, new in (
    ("<Version>0.1.64</Version>", "<Version>0.1.65</Version>"),
    ("<AssemblyVersion>0.1.64.0</AssemblyVersion>", "<AssemblyVersion>0.1.65.0</AssemblyVersion>"),
    ("<FileVersion>0.1.64.0</FileVersion>", "<FileVersion>0.1.65.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.64"' not in update:
    raise SystemExit("UpdateManager V0.1.64 marker missing")
update = update.replace('CurrentVersion = "V0.1.64"', 'CurrentVersion = "V0.1.65"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 5) Static invariants.
# ---------------------------------------------------------------------------
patched = read(engine_path)
for marker in (
    "V0165_ABYSS_DEATH_VISUAL_FALLBACK",
    "redRatio >= 0.050",
    "orangeRatio >= 0.160",
    "V0165_ABYSS_DEATH_POSTWAIT_RECHECK",
    "5분 후 재확인:",
    "던전 퇴장 취소, 현재 단계 정상 진행 재개",
    "5분 후에도 사망 화면 유지 -> 던전 퇴장 시작",
    "scene_skip 보류 -> 사망 화면 우선",
    "scene_skip 2/2 이미지 연속 확인",
    "Task.Delay(TimeSpan.FromMinutes(5), ct)",
    "실제 결과 화면 후보 1/2",
    "실제 결과 화면 2/2 확인",
    "회복 물약 팝업 ESC 후 닫힘 2프레임 확인",
    "V0163_GLOBAL_INPUT_LOCK",
    "V0164_ABYSS_CLEAR_LOG_SIMPLIFIED",
):
    if marker not in patched:
        raise SystemExit(f"required runtime marker missing: {marker}")

targets_check = json.loads(read(targets_path))
scene_check = next(t for t in targets_check if t.get("Id") == "scene_skip")
if scene_check.get("Kind") != "template":
    raise SystemExit("scene_skip must be template-only")
if scene_check.get("Roi") != {"X": 620, "Y": 20, "Width": 180, "Height": 90}:
    raise SystemExit("scene_skip ROI mismatch")
if float(scene_check.get("Threshold", 0)) < 0.74:
    raise SystemExit("scene_skip threshold too low")

# Restrict V0.1.65 changes to intended files only.
allowed = {
    engine_path.relative_to(root).as_posix(),
    targets_path.relative_to(root).as_posix(),
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

if "<Version>0.1.65</Version>" not in read(project_path):
    raise SystemExit("project version not V0.1.65")
if 'CurrentVersion = "V0.1.65"' not in read(update_path):
    raise SystemExit("updater version not V0.1.65")

print("V0.1.65 applied: death visual fallback + 5-minute post-wait recheck + scene-skip image-only death guard")
