#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0145_entry_state_hardening.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

engine = read(engine_path)

# 1) Selected/challenge classification: exact OCR only.
# Remove all visual fallback so an unrelated button image can never drive the state transition.
old_classify = '''        const double VisualLeadMargin = 0.07;

        // 800x1000 client coordinates.
'''
new_classify = '''        // V0.1.45: selected/challenge state is exact OCR only.
        // No visual-template fallback is allowed to drive a click.

        // 800x1000 client coordinates.
'''
engine = replace_once(engine, old_classify, new_classify, "remove visual lead margin")

old_body = '''            // Exact/near-exact text gets priority over visual similarity.
            var challengeText = await _detector.DetectAsync("challenge_confirm_strict", frame, ct);
            if (challengeText.Found)
                return (2, Point.Empty, 0.0, 1.0);

            var selectedText = await _detector.DetectAsync("selected_ocr_strict", frame, ct);
            if (selectedText.Found)
                return (1, selectedText.Center, 1.0, 0.0);

            // OCR failed: compare the two button images against each other.
            // A single loose template match is not enough to click anything.
            var selectedVisual = await _detector.DetectAsync("selected_red_visual", frame, ct);
            var challengeVisual = await _detector.DetectAsync("challenge_visual", frame, ct);

            double s = selectedVisual.Score;
            double c = challengeVisual.Score;

            if (selectedVisual.Found && challengeVisual.Found)
            {
                if (s >= c + VisualLeadMargin)
                    return (1, selectedVisual.Center, s, c);
                if (c >= s + VisualLeadMargin)
                    return (2, Point.Empty, s, c);
                return (0, Point.Empty, s, c);
            }

            if (selectedVisual.Found && !challengeVisual.Found)
                return (1, selectedVisual.Center, s, c);
            if (challengeVisual.Found && !selectedVisual.Found)
                return (2, Point.Empty, s, c);

            return (0, Point.Empty, s, c);
'''
new_body = '''            // Exact OCR only. If neither exact state word is present, do nothing.
            var challengeText = await _detector.DetectAsync("challenge_confirm_strict", frame, ct);
            if (challengeText.Found)
                return (2, Point.Empty, 0.0, 1.0);

            var selectedText = await _detector.DetectAsync("selected_ocr_strict", frame, ct);
            if (selectedText.Found)
                return (1, selectedText.Center, 1.0, 0.0);

            return (0, Point.Empty, 0.0, 0.0);
'''
engine = replace_once(engine, old_body, new_body, "exact OCR state classifier")

# 2) In the normal dungeon entry steps, do not run global monitors at all.
# This removes the full-screen scene_skip mouse-click path while waiting for / entering a dungeon.
old_monitor = '''            else
            {
                if (await CheckMonitorsAsync(frame, ct))
                    continue;

                if (step.Target.Equals("abyss_icon", StringComparison.OrdinalIgnoreCase) && abyssIconRejected.Count > 0)
'''
new_monitor = '''            else
            {
                bool dungeonEntryStep =
                    step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase) ||
                    step.Target.Equals("enter_confirm", StringComparison.OrdinalIgnoreCase);

                if (!dungeonEntryStep && await CheckMonitorsAsync(frame, ct))
                    continue;

                if (dungeonEntryStep)
                    Log?.Invoke($"[던전 입장] {step.Target} 단계에서는 scene_skip 포함 전역 모니터 클릭 비활성");

                if (step.Target.Equals("abyss_icon", StringComparison.OrdinalIgnoreCase) && abyssIconRejected.Count > 0)
'''
engine = replace_once(engine, old_monitor, new_monitor, "disable monitors in entry steps")

# 3) VerifyChallengeBeforeEntryAsync also used the global monitor twice.
# Remove both calls so selected->challenge verification cannot be interrupted by scene_skip.
old_verify_monitor = '''            if (await CheckMonitorsAsync(frame, ct))
            {
                challengeConsecutive = 0;
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            var state = await ClassifyAsync(frame);
'''
new_verify_monitor = '''            // Entry-state verification must not execute global click monitors.
            var state = await ClassifyAsync(frame);
'''
engine = replace_once(engine, old_verify_monitor, new_verify_monitor, "disable verifier monitor")

old_final_monitor = '''            if (await CheckMonitorsAsync(finalFrame, ct))
            {
                challengeConsecutive = 0;
                continue;
            }

            var finalState = await ClassifyAsync(finalFrame);
'''
new_final_monitor = '''            // Final entry confirmation is also monitor-free.
            var finalState = await ClassifyAsync(finalFrame);
'''
engine = replace_once(engine, old_final_monitor, new_final_monitor, "disable final verifier monitor")

# 4) Defense in depth: if scene_skip is called from recovery/another path while an
# entry screen is visible, suppress its click before the existing 2-frame confirmation.
scene_anchor = '''            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
            {
                Log?.Invoke($"[monitor] scene_skip 1/2 확인 ({r.ReadText ?? r.Score.ToString("0.000")}) -> 별도 프레임 재확인");
'''
scene_guard = '''            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
            {
                var entrySelected = await _detector.DetectAsync("selected_ocr_strict", frame, ct);
                var entryChallenge = await _detector.DetectAsync("challenge_confirm_strict", frame, ct);
                var entryButton = await _detector.DetectAsync("enter_bottom", frame, ct);

                if (entrySelected.Found || entryChallenge.Found || entryButton.Found)
                {
                    Log?.Invoke(
                        $"[monitor] 입장 화면 감지 -> scene_skip 클릭 차단 " +
                        $"selected={(entrySelected.Found ? 1 : 0)} " +
                        $"challenge={(entryChallenge.Found ? 1 : 0)} " +
                        $"enter={(entryButton.Found ? 1 : 0)}");
                    continue;
                }

                Log?.Invoke($"[monitor] scene_skip 1/2 확인 ({r.ReadText ?? r.Score.ToString("0.000")}) -> 별도 프레임 재확인");
'''
engine = replace_once(engine, scene_anchor, scene_guard, "scene_skip entry-screen suppression")

write(engine_path, engine)

# 5) Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.44", "V0.1.45")
                   .replace("0.1.44.0", "0.1.45.0")
                   .replace("0.1.44", "0.1.45"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.45_ENTRY_STATE_HARDENING.txt").write_text(
    "MABI AUTO V0.1.45 - ENTRY STATE HARDENING\n\n"
    "Selected/challenge classification is exact OCR only. The visual-template fallback is no longer allowed to drive a state click.\n"
    "While normal dungeon steps are waiting for or activating enter_bottom/enter_confirm, all global monitor clicks are disabled.\n"
    "VerifyChallengeBeforeEntryAsync is monitor-free, so scene_skip cannot click anything during selected -> challenge -> entry verification.\n"
    "Defense in depth: if scene_skip is invoked from another/recovery path and exact selected/challenge/entry text is visible, its click is suppressed.\n"
    "Selected-state click remains restricted to the dungeon-card safe region.\n"
    "Challenge + exact right-bottom entry still uses Space scan code 0x39; there is no mouse click for dungeon entry.\n"
    "Recognition nav UI remains '인식' with image icon.\n",
    encoding="utf-8"
)

check = read(engine_path)
required = (
    "selected/challenge state is exact OCR only",
    "Entry-state verification must not execute global click monitors",
    "Final entry confirmation is also monitor-free",
    "dungeonEntryStep",
    "scene_skip 포함 전역 모니터 클릭 비활성",
    "입장 화면 감지 -> scene_skip 클릭 차단",
    "도전 상태 + 오른쪽 입장하기 확인 -> Space 입력",
)
for marker in required:
    if marker not in check:
        raise RuntimeError("V0.1.45 marker missing: " + marker)

for forbidden in (
    'DetectAsync("selected_red_visual", frame, ct)',
    'DetectAsync("challenge_visual", frame, ct)',
    "VisualLeadMargin",
):
    if forbidden in check:
        raise RuntimeError("visual state fallback still present: " + forbidden)

print("V0.1.45 patch applied: exact OCR state + no scene_skip clicks during dungeon entry")
