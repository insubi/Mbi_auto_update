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
# 1) Add the video-derived scene-skip outline detector.
# Across the supplied recording the cinematic background changes heavily,
# but the long neutral-white rounded top border stays stable.
# ---------------------------------------------------------------------------
helper_anchor = "    // V0162_ABYSS_DEATH_EXIT_NO_REVIVE\n"
if helper_anchor not in engine:
    raise SystemExit("death helper anchor missing")

scene_helper = r'''    // V0166_ABYSS_SCENE_SKIP_OUTLINE
    private static DetectionResult DetectAbyssSceneSkipOutline(Bitmap frame)
    {
        Rectangle bounds = new(0, 0, frame.Width, frame.Height);
        Rectangle roi = Rectangle.Intersect(new Rectangle(620, 20, 180, 90), bounds);
        if (roi.Width < 80 || roi.Height < 30)
            return DetectionResult.NotFound;

        int bestRun = 0;
        int bestStartX = 0;
        int bestY = 0;

        for (int y = roi.Top; y < roi.Bottom; y++)
        {
            int run = 0;
            int runStart = roi.Left;

            for (int x = roi.Left; x < roi.Right; x++)
            {
                Color p = frame.GetPixel(x, y);
                int max = Math.Max(p.R, Math.Max(p.G, p.B));
                int min = Math.Min(p.R, Math.Min(p.G, p.B));

                bool neutralBright = min > 105 && max - min < 90;
                if (neutralBright)
                {
                    if (run == 0)
                        runStart = x;
                    run++;

                    if (run > bestRun)
                    {
                        bestRun = run;
                        bestStartX = runStart;
                        bestY = y;
                    }
                }
                else
                {
                    run = 0;
                }
            }
        }

        // Recorded real "장면 넘기기" frames had a ~99-112px continuous border.
        // Normal/death HUD samples stayed around 28px or less.
        if (bestRun < 75)
            return DetectionResult.NotFound;

        int left = Math.Max(roi.Left, bestStartX - 6);
        int top = Math.Max(roi.Top, bestY - 8);
        int width = Math.Min(frame.Width - left, bestRun + 12);
        int height = Math.Min(frame.Height - top, 48);

        return new DetectionResult(
            true,
            new Rectangle(left, top, width, height),
            Math.Min(1.0, bestRun / 105.0),
            $"scene-outline:{bestRun}");
    }

'''
engine = engine.replace(helper_anchor, scene_helper + helper_anchor, 1)

# ---------------------------------------------------------------------------
# 2) Fix the pre-filter bug in V0.1.65.
# Previously "if (!r.Found) continue" ran before the death visual fallback,
# so OCR failure could prevent the visual fallback from ever executing.
# Abyss scene-skip also bypasses the old background-sensitive template here.
# Normal dungeon behavior remains unchanged.
# ---------------------------------------------------------------------------
old_detect = '''            var r = await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
'''
new_detect = '''            bool abyssRuntime =
                string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);

            DetectionResult r;
            if (abyssRuntime &&
                m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
            {
                var preDeathVisual = DetectAbyssDeathVisualState(frame);
                if (preDeathVisual.Death && preDeathVisual.Revive)
                {
                    r = new DetectionResult(
                        true,
                        new Rectangle(300, 130, 200, 130),
                        Math.Min(1.0, (preDeathVisual.RedRatio / 0.050 +
                                       preDeathVisual.OrangeRatio / 0.160) / 2.0),
                        "death-visual-pair");
                }
                else
                {
                    r = await _detector.DetectAsync(m.Target, frame, ct);
                }
            }
            else if (abyssRuntime &&
                     m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
            {
                r = DetectAbyssSceneSkipOutline(frame);
            }
            else
            {
                r = await _detector.DetectAsync(m.Target, frame, ct);
            }

            if (!r.Found) continue;

            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
'''
if engine.count(old_detect) != 1:
    raise SystemExit("monitor pre-filter anchor mismatch")
engine = engine.replace(old_detect, new_detect, 1)

# ---------------------------------------------------------------------------
# 3) After the requested 5-minute wait, require death state on TWO fresh frames.
# If either recheck says the state changed, cancel the exit and let normal flow continue.
# ---------------------------------------------------------------------------
old_postwait = '''                using var postWaitFrame = await CaptureGameWindowAsync(ct);
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
'''
new_postwait = '''                using var postWaitFrame1 = await CaptureGameWindowAsync(ct);
                var deathAfter1 = await _detector.DetectAsync("abyss_death_state", postWaitFrame1, ct);
                var reviveAfter1 = await _detector.DetectAsync("abyss_revive_here", postWaitFrame1, ct);
                var visualAfter1 = DetectAbyssDeathVisualState(postWaitFrame1);
                bool stillDeath1 = (deathAfter1.Found || visualAfter1.Death) &&
                                   (reviveAfter1.Found || visualAfter1.Revive);

                if (!stillDeath1)
                {
                    var clearAfter = await DetectAbyssConfirmedClearAsync(postWaitFrame1, ct);
                    var resultAfter = await DetectAbyssResultRetryAsync(postWaitFrame1, ct);
                    string state = clearAfter.Found
                        ? "클리어 화면"
                        : resultAfter.Found
                            ? "결과/다시 하기 화면"
                            : "사망 화면 해제";

                    Log?.Invoke($"[어비스 사망] 5분 후 재확인 1/2: {state} -> 던전 퇴장 취소, 현재 단계 정상 진행 재개");
                    return true;
                }

                Log?.Invoke($"[어비스 사망] 5분 후 사망 상태 재확인 1/2 (visual red={visualAfter1.RedRatio:0.000}, orange={visualAfter1.OrangeRatio:0.000})");
                await Task.Delay(250, ct);

                using var postWaitFrame2 = await CaptureGameWindowAsync(ct);
                var deathAfter2 = await _detector.DetectAsync("abyss_death_state", postWaitFrame2, ct);
                var reviveAfter2 = await _detector.DetectAsync("abyss_revive_here", postWaitFrame2, ct);
                var visualAfter2 = DetectAbyssDeathVisualState(postWaitFrame2);
                bool stillDeath2 = (deathAfter2.Found || visualAfter2.Death) &&
                                   (reviveAfter2.Found || visualAfter2.Revive);

                if (!stillDeath2)
                {
                    Log?.Invoke("[어비스 사망] 5분 후 재확인 2/2 불일치 -> 던전 퇴장 취소, 현재 단계 정상 진행 재개");
                    return true;
                }

                Log?.Invoke($"[어비스 사망] 5분 후 사망 상태 2/2 유지 -> 던전 퇴장 시작 (visual red={visualAfter2.RedRatio:0.000}, orange={visualAfter2.OrangeRatio:0.000})");
'''
if engine.count(old_postwait) != 1:
    raise SystemExit("V0.1.65 post-wait death recheck anchor mismatch")
engine = engine.replace(old_postwait, new_postwait, 1)

# ---------------------------------------------------------------------------
# 4) Scene-skip confirmation must use the same outline detector on Abyss.
# The death-priority checks already present in V0.1.65 are preserved.
# ---------------------------------------------------------------------------
old_scene_confirm = '''                var confirm = await _detector.DetectAsync(m.Target, confirmFrame, ct);
                if (!confirm.Found)
'''
new_scene_confirm = '''                var confirm = abyssRuntime
                    ? DetectAbyssSceneSkipOutline(confirmFrame)
                    : await _detector.DetectAsync(m.Target, confirmFrame, ct);
                if (!confirm.Found)
'''
if engine.count(old_scene_confirm) != 1:
    raise SystemExit("scene confirmation anchor mismatch")
engine = engine.replace(old_scene_confirm, new_scene_confirm, 1)

write(engine_path, engine)

# ---------------------------------------------------------------------------
# 5) Version metadata.
# ---------------------------------------------------------------------------
project = read(project_path)
for old, new in (
    ("<Version>0.1.65</Version>", "<Version>0.1.66</Version>"),
    ("<AssemblyVersion>0.1.65.0</AssemblyVersion>", "<AssemblyVersion>0.1.66.0</AssemblyVersion>"),
    ("<FileVersion>0.1.65.0</FileVersion>", "<FileVersion>0.1.66.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.65"' not in update:
    raise SystemExit("UpdateManager V0.1.65 marker missing")
update = update.replace('CurrentVersion = "V0.1.65"', 'CurrentVersion = "V0.1.66"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 6) Static invariants.
# ---------------------------------------------------------------------------
patched = read(engine_path)
for marker in (
    "V0166_ABYSS_SCENE_SKIP_OUTLINE",
    "bestRun < 75",
    "death-visual-pair",
    "preDeathVisual.Death && preDeathVisual.Revive",
    "5분 후 사망 상태 재확인 1/2",
    "5분 후 사망 상태 2/2 유지 -> 던전 퇴장 시작",
    "DetectAbyssSceneSkipOutline(frame)",
    "DetectAbyssSceneSkipOutline(confirmFrame)",
    "V0165_ABYSS_DEATH_VISUAL_FALLBACK",
    "V0165_ABYSS_DEATH_POSTWAIT_RECHECK",
    "scene_skip 보류 -> 사망 화면 우선",
    "V0164_ABYSS_CLEAR_LOG_SIMPLIFIED",
    "실제 결과 화면 2/2 확인",
    "회복 물약 팝업 ESC 후 닫힘 2프레임 확인",
):
    if marker not in patched:
        raise SystemExit(f"required runtime marker missing: {marker}")

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

print("V0.1.66 applied: death visual pre-filter fix + two-frame post-wait recheck + video outline scene-skip")
