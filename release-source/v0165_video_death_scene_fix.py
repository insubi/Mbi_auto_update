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
# 1) Video-derived visual detectors.
#    Death OCR missed the real screen in two recordings, so use stable UI colors:
#      - red "행동불능" center text
#      - orange "여기서 부활" button
#    Scene-skip uses the long neutral-white top border of the actual button.
#    This avoids the previous OCR false positive on normal top-right HUD.
# ---------------------------------------------------------------------------
helper_anchor = "    // V0162_ABYSS_DEATH_EXIT_NO_REVIVE\n"
if helper_anchor not in engine:
    raise SystemExit("death helper anchor missing")

helpers = r'''    // V0165_ABYSS_VIDEO_VISUAL_DETECTORS
    private static (DetectionResult Death, DetectionResult Revive) DetectAbyssDeathVisualPair(Bitmap frame)
    {
        Rectangle bounds = new(0, 0, frame.Width, frame.Height);

        Rectangle deathRoi = Rectangle.Intersect(new Rectangle(280, 130, 220, 100), bounds);
        int redSamples = 0;
        for (int y = deathRoi.Top; y < deathRoi.Bottom; y += 2)
        {
            for (int x = deathRoi.Left; x < deathRoi.Right; x += 2)
            {
                Color p = frame.GetPixel(x, y);
                if (p.R > 150 &&
                    p.R - p.G > 60 &&
                    p.R - p.B > 70 &&
                    p.G < 140)
                {
                    redSamples++;
                }
            }
        }

        Rectangle reviveRoi = Rectangle.Intersect(new Rectangle(220, 760, 210, 120), bounds);
        int orangeSamples = 0;
        for (int y = reviveRoi.Top; y < reviveRoi.Bottom; y += 2)
        {
            for (int x = reviveRoi.Left; x < reviveRoi.Right; x += 2)
            {
                Color p = frame.GetPixel(x, y);
                if (p.R > 170 &&
                    p.G > 60 && p.G < 190 &&
                    p.B < 120 &&
                    p.R - p.G > 45 &&
                    p.R - p.B > 70)
                {
                    orangeSamples++;
                }
            }
        }

        bool deathFound = redSamples >= 350;
        bool reviveFound = orangeSamples >= 900;

        var death = deathFound
            ? new DetectionResult(
                true,
                new Rectangle(300, 145, 170, 70),
                Math.Min(1.0, redSamples / 500.0),
                $"death-red:{redSamples}")
            : DetectionResult.NotFound;

        var revive = reviveFound
            ? new DetectionResult(
                true,
                new Rectangle(235, 790, 180, 75),
                Math.Min(1.0, orangeSamples / 1300.0),
                $"revive-orange:{orangeSamples}")
            : DetectionResult.NotFound;

        return (death, revive);
    }

    private static DetectionResult DetectAbyssSceneSkipVisual(Bitmap frame)
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

                // Actual "장면 넘기기" button has a long neutral-white rounded border.
                // Normal Home/End/ESC HUD contains short icon/text strokes instead.
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
engine = engine.replace(helper_anchor, helpers + helper_anchor, 1)

# ---------------------------------------------------------------------------
# 2) Replace the Abyss death monitor with video-derived visual confirmation.
#    Preserve 2-frame confirmation and the 5-minute delay, but after 5 minutes
#    require death to STILL be present for 2 fresh frames. If revived or the
#    screen advanced, cancel the exit and continue the current run.
# ---------------------------------------------------------------------------
old_death_block = '''            var r = await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
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

            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
'''
new_death_block = '''            bool abyssRuntime =
                string.Equals(new DirectoryInfo(_baseDir).Name, "abyss", StringComparison.OrdinalIgnoreCase);

            if (abyssRuntime &&
                m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
            {
                var firstDeath = DetectAbyssDeathVisualPair(frame);
                if (!firstDeath.Death.Found || !firstDeath.Revive.Found)
                    continue;

                Log?.Invoke($"[어비스 사망] 영상기준 사망 화면 후보 1/2 ({firstDeath.Death.ReadText}, {firstDeath.Revive.ReadText})");
                await Task.Delay(250, ct);

                using var deathConfirmFrame = await CaptureGameWindowAsync(ct);
                var secondDeath = DetectAbyssDeathVisualPair(deathConfirmFrame);
                if (!secondDeath.Death.Found || !secondDeath.Revive.Found)
                {
                    Log?.Invoke("[어비스 사망] 2차 확인 실패 -> 아무 입력도 하지 않음");
                    continue;
                }

                _monitorLastAction[m.Target] = Environment.TickCount64;
                Log?.Invoke("[어비스 사망] 행동불능 + 여기서 부활 2/2 확인 -> 5분 대기 후 상태 재확인");
                await Task.Delay(TimeSpan.FromMinutes(5), ct);

                using var afterWaitFrame1 = await CaptureGameWindowAsync(ct);
                var afterWait1 = DetectAbyssDeathVisualPair(afterWaitFrame1);
                if (!afterWait1.Death.Found || !afterWait1.Revive.Found)
                {
                    Log?.Invoke("[어비스 사망] 5분 후 사망 상태가 해제되었거나 화면이 전환됨 -> 퇴장 취소, 현재 진행 계속");
                    return true;
                }

                await Task.Delay(250, ct);
                using var afterWaitFrame2 = await CaptureGameWindowAsync(ct);
                var afterWait2 = DetectAbyssDeathVisualPair(afterWaitFrame2);
                if (!afterWait2.Death.Found || !afterWait2.Revive.Found)
                {
                    Log?.Invoke("[어비스 사망] 5분 후 사망 상태 2차 확인 불일치 -> 퇴장 취소, 현재 진행 계속");
                    return true;
                }

                Log?.Invoke("[어비스 사망] 5분 대기 완료 + 사망 상태 2/2 유지 -> 던전 퇴장 시작");
                await HandleAbyssDeathExitAsync(ct);
                throw new RestartCycleException();
            }

            DetectionResult r = abyssRuntime &&
                                m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase)
                ? DetectAbyssSceneSkipVisual(frame)
                : await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
'''
if engine.count(old_death_block) != 1:
    raise SystemExit("current V0.1.64 death-monitor block anchor mismatch")
engine = engine.replace(old_death_block, new_death_block, 1)

# For Abyss scene-skip, the second frame must use the same border detector.
old_scene_confirm = '''                var confirm = await _detector.DetectAsync(m.Target, confirmFrame, ct);
                if (!confirm.Found)
'''
new_scene_confirm = '''                var confirm = abyssRuntime
                    ? DetectAbyssSceneSkipVisual(confirmFrame)
                    : await _detector.DetectAsync(m.Target, confirmFrame, ct);
                if (!confirm.Found)
'''
if engine.count(old_scene_confirm) != 1:
    raise SystemExit("scene-skip confirmation anchor mismatch")
engine = engine.replace(old_scene_confirm, new_scene_confirm, 1)
write(engine_path, engine)

# ---------------------------------------------------------------------------
# 3) Version metadata.
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
# 4) Static invariants.
# ---------------------------------------------------------------------------
patched = read(engine_path)
for marker in (
    "V0165_ABYSS_VIDEO_VISUAL_DETECTORS",
    "redSamples >= 350",
    "orangeSamples >= 900",
    "bestRun < 75",
    "영상기준 사망 화면 후보 1/2",
    "5분 대기 후 상태 재확인",
    "5분 후 사망 상태가 해제되었거나 화면이 전환됨 -> 퇴장 취소",
    "5분 대기 완료 + 사망 상태 2/2 유지 -> 던전 퇴장 시작",
    "DetectAbyssSceneSkipVisual(frame)",
    "scene_skip 2/2 연속 확인",
    "V0164_ABYSS_CLEAR_LOG_SIMPLIFIED",
    "실제 결과 화면 후보 1/2",
    "실제 결과 화면 2/2 확인",
    "회복 물약 팝업 ESC 후 닫힘 2프레임 확인",
):
    if marker not in patched:
        raise SystemExit(f"required runtime marker missing: {marker}")

if "5분 대기 완료 -> 던전 퇴장 시작" in patched:
    raise SystemExit("old unconditional 5-minute death exit log/path remains")

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

print("V0.1.65 applied: video-derived Abyss death detection + safe 5-minute recheck + scene-skip outline detector")
