#!/usr/bin/env python3
from pathlib import Path
import base64
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0122_dungeon_challenge_semantics.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
scenario_path = app / "dungeon" / "config" / "scenario.json"
targets_path = app / "dungeon" / "config" / "targets.json"
template_dir = app / "dungeon" / "templates"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


# Red '선택됨' state cropped from the user's 800x1000-equivalent failure screenshot.
# TemplateMatcher works in grayscale, while OCR remains as fallback.
selected_red_b64 = "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"

template_dir.mkdir(parents=True, exist_ok=True)
(template_dir / "selected_red_visual.png").write_bytes(base64.b64decode(selected_red_b64))

# Keep V0.1.21's robust challenge hybrid detector, but make 'selected' hybrid too.
targets = json.loads(read(targets_path))
selected = next((t for t in targets if t.get("Id") == "selected"), None)
challenge = next((t for t in targets if t.get("Id") == "challenge"), None)
if selected is None or challenge is None:
    raise RuntimeError("selected/challenge target missing")
selected["Kind"] = "hybrid"
selected["TemplatePath"] = "templates/selected_red_visual.png"
selected["Threshold"] = 0.60
selected["TemplateScaleMin"] = 0.72
selected["TemplateScaleMax"] = 1.28
selected["TemplateScaleStep"] = 0.04
selected["Text"] = "선택됨"
selected["MaxEditDistance"] = 1
selected["OcrRetryAt2x"] = True
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# Step 1 only waits until the bottom entry button is present. State semantics are
# checked immediately before entry by VerifyChallengeBeforeEntryAsync.
scenario = json.loads(read(scenario_path))
step1 = scenario["Steps"][0]
step1["Name"] = "1. 입장 화면 확인"
step1["Type"] = "wait"
step1["Target"] = "enter_bottom"
step1["TimeoutSeconds"] = 45
step1.pop("AlternativeTarget", None)
step1.pop("ClickAlternativeThenWaitPrimary", None)
write(scenario_path, json.dumps(scenario, ensure_ascii=False, indent=2) + "\n")

# Correct semantics: '선택됨' is NOT the enter-ready state. Click it once so the
# button returns to '도전'. Only a stable '도전' state authorizes the following
# enter_bottom click. This restores the pre-V0.1.21 behavior while adding robust
# red selected-state recognition.
engine = read(engine_path)
start_marker = "    // DUNGEON_ENTRY_READY_GUARD_V3\n    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)\n"
next_marker = "    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)\n"
start = engine.find(start_marker)
end = engine.find(next_marker)
if start < 0 or end < 0 or end <= start:
    raise RuntimeError("could not locate V0.1.21 dungeon entry guard")

new_guard = '''    // DUNGEON_CHALLENGE_SEMANTICS_V4
    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)
    {
        const int RequiredConsecutive = 3;
        const int ConfirmIntervalMs = 300;
        const int FinalDelayMs = 1000;
        const int MaxVerifySeconds = 45;

        int challengeConsecutive = 0;
        long lastSelectedClick = 0;
        var verifyTimer = Stopwatch.StartNew();

        Log?.Invoke("[던전 입장확인] 도전 상태 검증 시작: 선택됨이면 해제, 도전이면 입장 허용");

        while (verifyTimer.Elapsed < TimeSpan.FromSeconds(MaxVerifySeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(frame, ct))
            {
                challengeConsecutive = 0;
                continue;
            }

            // IMPORTANT: selected is checked first so a selected stage can never be
            // authorized as '도전' by a loose visual match.
            var selected = await _detector.DetectAsync("selected", frame, ct);
            if (selected.Found)
            {
                challengeConsecutive = 0;
                long now = Environment.TickCount64;
                if (now - lastSelectedClick >= 1200)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[던전 입장확인] 선택됨 확인 -> 도전 상태로 전환 위해 1회 클릭 @ {selected.Bounds} score={selected.Score:0.000}");
                    _input.ClickClientPoint(_hwnd, selected.Center);
                    lastSelectedClick = now;
                    await Task.Delay(Math.Max(650, _settings.ClickSettleMs), ct);
                }
                else
                {
                    await Task.Delay(ConfirmIntervalMs, ct);
                }
                continue;
            }

            var challenge = await _detector.DetectAsync("challenge", frame, ct);
            if (!challenge.Found)
            {
                if (challengeConsecutive > 0)
                    Log?.Invoke($"[던전 입장확인] 도전 연속 확인 끊김 ({challengeConsecutive}/{RequiredConsecutive})");
                challengeConsecutive = 0;
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            challengeConsecutive++;
            Log?.Invoke($"[던전 입장확인] 도전 확인 {challengeConsecutive}/{RequiredConsecutive} score={challenge.Score:0.000}");

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

            var finalSelected = await _detector.DetectAsync("selected", finalFrame, ct);
            if (finalSelected.Found)
            {
                Log?.Invoke("[던전 입장확인] 최종 확인에서 선택됨 재발견 -> 입장 보류");
                challengeConsecutive = 0;
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            var finalChallenge = await _detector.DetectAsync("challenge", finalFrame, ct);
            if (finalChallenge.Found)
            {
                Log?.Invoke($"[던전 입장확인] 최종 도전 확인 성공 -> 입장하기 허용 score={finalChallenge.Score:0.000}");
                return;
            }

            Log?.Invoke("[던전 입장확인] 최종 도전 확인 실패 -> 다시 확인");
            challengeConsecutive = 0;
            await Task.Delay(ConfirmIntervalMs, ct);
        }

        throw new TimeoutException(
            "45초 동안 선택됨 해제 후 도전 상태를 안정적으로 확인하지 못했습니다.");
    }
'''
engine = engine[:start] + new_guard + engine[end:]

required = [
    "DUNGEON_CHALLENGE_SEMANTICS_V4",
    "선택됨 확인 -> 도전 상태로 전환 위해 1회 클릭",
    "도전 확인 {challengeConsecutive}/{RequiredConsecutive}",
    "최종 도전 확인 성공 -> 입장하기 허용",
    "selected_red_visual.png",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]
for marker in required:
    if marker not in engine and marker != "selected_red_visual.png":
        raise RuntimeError(f"required V0.1.22 engine marker missing: {marker}")
write(engine_path, engine)

# Version bump only runtime/source files; leave historical changelog text untouched.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (
        text.replace("V0.1.21", "V0.1.22")
        .replace("0.1.21.0", "0.1.22.0")
        .replace("0.1.21", "0.1.22")
    )
    if changed != text:
        write(path, changed)

changes = root / "CHANGES_V0.1.22_DUNGEON_CHALLENGE_SEMANTICS.txt"
changes.write_text(
    "MABI AUTO V0.1.22 - DUNGEON CHALLENGE SEMANTICS\n"
    "\n"
    "Base: V0.1.21.\n"
    "Correction: '도전' is the state that authorizes dungeon entry. V0.1.21 had this reversed.\n"
    "When '선택됨' is visible, the bot clicks it once and waits until it changes to '도전'.\n"
    "Only after '도전' is confirmed for 3 consecutive frames plus a final check does the bot allow the bottom '입장하기' click.\n"
    "A red '선택됨' visual template from the reported failure screen was added, with OCR fallback, so red-state OCR misses no longer stall for 90 seconds.\n"
    "The existing challenge visual/OCR detector remains enabled for the challenge state.\n"
    "V0.1.20 Abyss outside-HUD quorum, V0.1.19 Abyss misclick guard, and fishing logic are preserved.\n",
    encoding="utf-8",
)

print("V0.1.22 applied: selected -> click once -> wait challenge; challenge -> allow entry")
