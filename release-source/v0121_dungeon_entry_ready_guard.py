#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0121_dungeon_entry_ready_guard.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
scenario_path = app / "dungeon" / "config" / "scenario.json"
targets_path = app / "dungeon" / "config" / "targets.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


# 1) Make the small '도전' button detector use the existing visual template first,
#    with OCR as fallback. The previous OCR-only detector is fragile on small antialiased text.
targets = json.loads(read(targets_path))
challenge = next((t for t in targets if t.get("Id") == "challenge"), None)
challenge_visual = next((t for t in targets if t.get("Id") == "challenge_visual"), None)
if challenge is None or challenge_visual is None:
    raise RuntimeError("challenge/challenge_visual target missing")
challenge["Kind"] = "hybrid"
challenge["TemplatePath"] = challenge_visual["TemplatePath"]
challenge["Threshold"] = challenge_visual.get("Threshold", 0.68)
challenge["TemplateScaleMin"] = challenge_visual.get("TemplateScaleMin", 0.75)
challenge["TemplateScaleMax"] = challenge_visual.get("TemplateScaleMax", 1.25)
challenge["TemplateScaleStep"] = challenge_visual.get("TemplateScaleStep", 0.05)
challenge["Text"] = "도전"
challenge["MaxEditDistance"] = 1
challenge["OcrRetryAt2x"] = True
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# 2) Step 1 should wait for the large, readable bottom '입장하기' state instead of
#    depending on tiny '도전/선택됨' OCR. If the bottom text is not ready but the
#    challenge button is visible, generic alternative handling may click it.
scenario = json.loads(read(scenario_path))
if not scenario.get("Steps"):
    raise RuntimeError("dungeon scenario has no steps")
step1 = scenario["Steps"][0]
if step1.get("Name") != "1. 도전 상태 확인":
    raise RuntimeError(f"unexpected first dungeon step: {step1}")
step1["Name"] = "1. 입장 준비 확인"
step1["Type"] = "wait"
step1["Target"] = "enter_bottom"
step1["TimeoutSeconds"] = 45
step1["AlternativeTarget"] = "challenge"
step1["ClickAlternativeThenWaitPrimary"] = True
write(scenario_path, json.dumps(scenario, ensure_ascii=False, indent=2) + "\n")

# 3) Replace the pre-entry guard. Old behavior required '도전' OCR to be stable and
#    treated '선택됨' as a state that must be clicked away. In the real UI, the screenshot
#    shows '선택됨' + enabled '입장하기' as the ready-to-enter state. New behavior:
#      - if '도전' is detected (template/OCR), click it to select the stage;
#      - otherwise require the large bottom '입장하기' text to be stable;
#      - '선택됨' OCR is telemetry only, not a hard requirement;
#      - final verification rejects any frame where '도전' reappears.
engine = read(engine_path)
start_marker = "    // STABLE_CHALLENGE_GUARD_V2_METHOD\n    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)\n"
next_marker = "    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)\n"
start = engine.find(start_marker)
end = engine.find(next_marker)
if start < 0 or end < 0 or end <= start:
    raise RuntimeError("could not locate challenge guard method block")

new_guard = '''    // DUNGEON_ENTRY_READY_GUARD_V3
    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)
    {
        const int RequiredConsecutive = 3;
        const int ConfirmIntervalMs = 300;
        const int FinalDelayMs = 1000;
        const int MaxVerifySeconds = 45;

        int readyConsecutive = 0;
        long lastChallengeClick = 0;
        var verifyTimer = Stopwatch.StartNew();

        Log?.Invoke("[던전 입장확인] 입장 준비 상태 검증 시작");

        while (verifyTimer.Elapsed < TimeSpan.FromSeconds(MaxVerifySeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(frame, ct))
            {
                readyConsecutive = 0;
                continue;
            }

            var challenge = await _detector.DetectAsync("challenge", frame, ct);
            if (challenge.Found)
            {
                readyConsecutive = 0;
                long now = Environment.TickCount64;
                if (now - lastChallengeClick >= 1200)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[던전 입장확인] 도전 버튼 확인 -> 선택 위해 클릭 @ {challenge.Bounds} score={challenge.Score:0.000}");
                    _input.ClickClientPoint(_hwnd, challenge.Center);
                    lastChallengeClick = now;
                    await Task.Delay(Math.Max(600, _settings.ClickSettleMs), ct);
                }
                else
                {
                    await Task.Delay(ConfirmIntervalMs, ct);
                }
                continue;
            }

            var enter = await _detector.DetectAsync("enter_bottom", frame, ct);
            var selected = await _detector.DetectAsync("selected", frame, ct);

            if (!enter.Found)
            {
                if (readyConsecutive > 0)
                    Log?.Invoke($"[던전 입장확인] 입장하기 연속 확인 끊김 ({readyConsecutive}/{RequiredConsecutive})");
                readyConsecutive = 0;
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            readyConsecutive++;
            Log?.Invoke($"[던전 입장확인] 입장하기 확인 {readyConsecutive}/{RequiredConsecutive}, 선택됨OCR={(selected.Found ? "Y" : "N")}");

            if (readyConsecutive < RequiredConsecutive)
            {
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            await Task.Delay(FinalDelayMs, ct);
            using var finalFrame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(finalFrame, ct))
            {
                readyConsecutive = 0;
                continue;
            }

            var finalChallenge = await _detector.DetectAsync("challenge", finalFrame, ct);
            var finalEnter = await _detector.DetectAsync("enter_bottom", finalFrame, ct);
            var finalSelected = await _detector.DetectAsync("selected", finalFrame, ct);

            if (!finalChallenge.Found && finalEnter.Found)
            {
                Log?.Invoke($"[던전 입장확인] 최종 확인 성공 -> 입장 허용, 선택됨OCR={(finalSelected.Found ? "Y" : "N")}");
                return;
            }

            Log?.Invoke($"[던전 입장확인] 최종 확인 보류: challenge={(finalChallenge.Found ? 1 : 0)} enter={(finalEnter.Found ? 1 : 0)}");
            readyConsecutive = 0;
            await Task.Delay(ConfirmIntervalMs, ct);
        }

        throw new TimeoutException(
            "45초 동안 도전 선택/입장하기 준비 상태를 안정적으로 확인하지 못했습니다.");
    }
'''
engine = engine[:start] + new_guard + engine[end:]

required_engine = [
    "DUNGEON_ENTRY_READY_GUARD_V3",
    "도전 버튼 확인 -> 선택 위해 클릭",
    "입장하기 확인 {readyConsecutive}/{RequiredConsecutive}",
    "선택됨OCR=",
    "!finalChallenge.Found && finalEnter.Found",
    "45초 동안 도전 선택/입장하기 준비 상태",
    "VerifyAbyssSelectionScreenAsync",
    "던전 밖 HUD 3/4 이상 확인",
    "어비스 클릭 검증 실패",
]
for marker in required_engine:
    if marker not in engine:
        raise RuntimeError(f"required V0.1.21 engine marker missing: {marker}")
write(engine_path, engine)

# 4) Runtime version bump, preserving historical text changelogs.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (
        text.replace("V0.1.20", "V0.1.21")
        .replace("0.1.20.0", "0.1.21.0")
        .replace("0.1.20", "0.1.21")
    )
    if changed != text:
        write(path, changed)

changes = root / "CHANGES_V0.1.21_DUNGEON_ENTRY_READY_GUARD.txt"
changes.write_text(
    "MABI AUTO V0.1.21 - DUNGEON ENTRY READY GUARD\n"
    "\n"
    "Base: V0.1.20.\n"
    "Root cause: dungeon step 1 depended on tiny OCR text for both '도전' and '선택됨'. The provided failure screenshot visibly shows '선택됨' and '입장하기', but the OCR-only selected target was not accepted within 90 seconds.\n"
    "Fix 1: challenge detection now uses the existing challenge_visual.png template first and OCR as fallback.\n"
    "Fix 2: step 1 waits for the large bottom '입장하기' text instead of tiny selected/challenge OCR.\n"
    "Fix 3: pre-entry guard clicks '도전' when visible, then accepts stable '입장하기' with challenge absent. '선택됨' OCR is telemetry only.\n"
    "Fix 4: guard timeout reduced from 90s to 45s with explicit state logs.\n"
    "V0.1.20 Abyss outside-HUD quorum, V0.1.19 Abyss misclick guard, and fishing logic are preserved.\n",
    encoding="utf-8",
)

print("V0.1.21 applied: dungeon challenge visual fallback + entry-ready state guard")
