#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0124_dungeon_selected_challenge_disambiguation.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
targets_path = app / "dungeon" / "config" / "targets.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


# Keep the existing V0.1.23 targets for compatibility/recovery, but add dedicated
# OCR-only and template-only detectors for entry-state classification. This prevents
# the hybrid 'selected' detector from matching the visually similar 'challenge' button.
targets = json.loads(read(targets_path))
by_id = {t.get("Id"): t for t in targets}
selected = by_id.get("selected")
challenge_visual = by_id.get("challenge_visual")
if selected is None or challenge_visual is None:
    raise RuntimeError("selected/challenge_visual targets missing")

roi = dict(selected.get("Roi") or {"X": 455, "Y": 700, "Width": 210, "Height": 115})

selected_ocr = {
    "Id": "selected_ocr_strict",
    "Kind": "ocr",
    "Roi": roi,
    "Text": "선택됨",
    "MaxEditDistance": 1,
    "OcrRetryAt2x": True,
}
selected_visual = {
    "Id": "selected_red_visual",
    "Kind": "template",
    "Roi": roi,
    "TemplatePath": "templates/selected_red_visual.png",
    "Threshold": 0.70,
    "TemplateScaleMin": 0.82,
    "TemplateScaleMax": 1.18,
    "TemplateScaleStep": 0.03,
}

# Replace if a previous experimental target exists, otherwise append.
def upsert(target):
    for i, old in enumerate(targets):
        if old.get("Id") == target["Id"]:
            targets[i] = target
            return
    targets.append(target)

upsert(selected_ocr)
upsert(selected_visual)
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

engine = read(engine_path)
start_marker = "    // DUNGEON_CHALLENGE_SEMANTICS_V4\n"
next_marker = "    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)\n"
start = engine.find(start_marker)
end = engine.find(next_marker)
if start < 0 or end < 0 or end <= start:
    raise RuntimeError("could not locate V0.1.23 challenge guard")

new_guard = '''    // DUNGEON_CHALLENGE_DISAMBIGUATION_V5
    // Entry rule: selected -> click once -> challenge confirmed -> enter.
    // Never click when selected/challenge visual evidence is ambiguous.
    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)
    {
        const int RequiredConsecutive = 3;
        const int ConfirmIntervalMs = 300;
        const int FinalDelayMs = 800;
        const int MaxVerifySeconds = 45;
        const double VisualLeadMargin = 0.07;

        int challengeConsecutive = 0;
        long lastSelectedClick = 0;
        long lastAmbiguousLog = 0;
        var timer = Stopwatch.StartNew();

        Log?.Invoke("[도전 안전확인] 선택됨/도전 분리 판정 시작");

        async Task<(int State, Point ClickPoint, double SelectedScore, double ChallengeScore)> ClassifyAsync(Bitmap frame)
        {
            // Exact/near-exact text gets priority over visual similarity.
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
        }

        while (timer.Elapsed < TimeSpan.FromSeconds(MaxVerifySeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(frame, ct))
            {
                challengeConsecutive = 0;
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            var state = await ClassifyAsync(frame);

            if (state.State == 1) // selected
            {
                challengeConsecutive = 0;
                long now = Environment.TickCount64;
                if (now - lastSelectedClick >= 1200)
                {
                    Log?.Invoke($"[도전 안전확인] 선택됨 확정 S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000} -> 1회 클릭");
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _input.ClickClientPoint(_hwnd, state.ClickPoint);
                    lastSelectedClick = now;
                    await Task.Delay(Math.Max(650, _settings.ClickSettleMs), ct);
                }
                else
                {
                    await Task.Delay(ConfirmIntervalMs, ct);
                }
                continue;
            }

            if (state.State == 0) // ambiguous / unknown
            {
                challengeConsecutive = 0;
                long now = Environment.TickCount64;
                if (now - lastAmbiguousLog >= 1500)
                {
                    Log?.Invoke($"[도전 안전확인] 판정 보류 S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000} -> 클릭 안 함");
                    lastAmbiguousLog = now;
                }
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            // challenge: do NOT click the challenge/selected toggle anymore.
            challengeConsecutive++;
            Log?.Invoke($"[도전 안전확인] 도전 확정 {challengeConsecutive}/{RequiredConsecutive} S={state.SelectedScore:0.000} C={state.ChallengeScore:0.000}");

            if (challengeConsecutive < RequiredConsecutive)
            {
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            await Task.Delay(FinalDelayMs, ct);
            using var finalFrame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(finalFrame, ct))
            {
                challengeConsecutive = 0;
                continue;
            }

            var finalState = await ClassifyAsync(finalFrame);
            var enter = await _detector.DetectAsync("enter_bottom", finalFrame, ct);

            if (finalState.State == 2 && enter.Found)
            {
                Log?.Invoke($"[도전 안전확인] 최종 도전 확인 성공 + 입장하기 확인 -> 입장 허용 (S={finalState.SelectedScore:0.000} C={finalState.ChallengeScore:0.000})");
                return;
            }

            Log?.Invoke($"[도전 안전확인] 최종 확인 보류 state={finalState.State} enter={(enter.Found ? 1 : 0)} S={finalState.SelectedScore:0.000} C={finalState.ChallengeScore:0.000}");
            challengeConsecutive = 0;
            await Task.Delay(ConfirmIntervalMs, ct);
        }

        throw new TimeoutException(
            "45초 동안 선택됨 -> 도전 -> 입장하기 상태를 안정적으로 확인하지 못했습니다.");
    }
'''

engine = engine[:start] + new_guard + engine[end:]

required = [
    "DUNGEON_CHALLENGE_DISAMBIGUATION_V5",
    "VisualLeadMargin = 0.07",
    "selected_ocr_strict",
    "selected_red_visual",
    "판정 보류",
    "challenge: do NOT click",
    "최종 도전 확인 성공 + 입장하기 확인",
    "DetectKnownDungeonRecoveryStepAsync",
    "ESC 1회 입력",
    "다시하기 확인 ->",
    "입장하기만 확인 -> 안전하게 도전 상태 확인",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]
for marker in required:
    if marker not in engine:
        raise RuntimeError(f"required V0.1.24 marker missing: {marker}")

if "DUNGEON_CHALLENGE_SEMANTICS_V4" in engine:
    raise RuntimeError("old V4 entry guard still present")

write(engine_path, engine)

# Runtime version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.23", "V0.1.24")
                   .replace("0.1.23.0", "0.1.24.0")
                   .replace("0.1.23", "0.1.24"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.24_DUNGEON_SELECTED_CHALLENGE_DISAMBIGUATION.txt").write_text(
    "MABI AUTO V0.1.24 - DUNGEON SELECTED/CHALLENGE DISAMBIGUATION\n\n"
    "Base: V0.1.23 state-aware ESC recovery.\n"
    "Fixes selected/challenge toggle clicking loop.\n"
    "Adds OCR-only selected detection and template-only red-selected detection for entry classification.\n"
    "Compares selected and challenge visual scores; ambiguous visual evidence never causes a click.\n"
    "Once challenge is confirmed, the toggle is not clicked again. Entry is allowed only after stable challenge confirmation plus enter-bottom detection.\n"
    "V0.1.23 state-aware ESC recovery, Abyss recovery, and fishing behavior are preserved.\n",
    encoding="utf-8"
)

print("V0.1.24 applied: selected/challenge disambiguation with no-click ambiguity guard")
