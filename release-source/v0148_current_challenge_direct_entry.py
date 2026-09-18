#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0148_current_challenge_direct_entry.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

engine = read(engine_path)

start_marker = "    // DUNGEON_CHALLENGE_DISAMBIGUATION_V5\n"
next_marker = "    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)\n"
start = engine.find(start_marker)
end = engine.find(next_marker, start)
if start < 0 or end < 0 or end <= start:
    raise RuntimeError("could not locate current dungeon entry verifier")

new_guard = r'''    // DUNGEON_CURRENT_CHALLENGE_DIRECT_ENTRY_V9
    // Current-screen rule:
    // 1) exact '도전' + exact right-bottom '입장하기' means the screen is already ready;
    //    do not require a prior '선택됨' observation.
    // 2) exact '선택됨' is clicked only inside the dungeon-card safe region to change it to '도전'.
    // 3) entry itself is still performed later by Space only; no mouse click is used for '입장하기'.
    // 4) strict retry OCR is checked only after every entry-state signal is absent.
    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)
    {
        const int RequiredReadyFrames = 2;
        const int ConfirmIntervalMs = 250;
        const int MaxVerifySeconds = 45;

        var selectedClickSafe = new Rectangle(430, 640, 330, 230);
        var entryKeySafe = new Rectangle(360, 900, 440, 100);

        int readyConsecutive = 0;
        int normalResultRetryClicks = 0;
        long lastSelectedClick = 0;
        long lastStateLog = 0;
        var timer = Stopwatch.StartNew();

        Log?.Invoke("[도전 안전확인] 현재 화면 우선 판정 시작: 도전+입장하기면 즉시 입장 흐름");

        while (timer.Elapsed < TimeSpan.FromSeconds(MaxVerifySeconds))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            // Entry state always wins over retry/result handling.
            var challenge = await _detector.DetectAsync("challenge_confirm_strict", frame, ct);
            var enter = await _detector.DetectAsync("enter_bottom", frame, ct);
            var selected = await _detector.DetectAsync("selected_ocr_strict", frame, ct);

            if (challenge.Found && enter.Found)
            {
                if (!entryKeySafe.Contains(enter.Center))
                {
                    readyConsecutive = 0;
                    Log?.Invoke($"[도전 안전확인] 도전+입장하기 감지했지만 입장하기가 안전영역 밖 -> 대기 @ {enter.Center} safe={entryKeySafe}");
                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                readyConsecutive++;
                Log?.Invoke(
                    $"[도전 안전확인] 현재 도전 상태 + 오른쪽 입장하기 확인 {readyConsecutive}/{RequiredReadyFrames} " +
                    $"challenge={challenge.Bounds} enter={enter.Bounds}");

                if (readyConsecutive >= RequiredReadyFrames)
                {
                    Log?.Invoke("[도전 안전확인] 현재 화면이 이미 도전 상태 -> 선택됨 이력 없이 바로 입장 허용");
                    return;
                }

                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            readyConsecutive = 0;

            // Selected means the toggle still needs one safe card click to return to challenge.
            if (selected.Found)
            {
                if (!selectedClickSafe.Contains(selected.Center))
                {
                    Log?.Invoke($"[도전 안전확인] 선택됨 검출 좌표가 카드 안전영역 밖 -> 클릭 안 함 @ {selected.Center} safe={selectedClickSafe}");
                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                long now = Environment.TickCount64;
                if (now - lastSelectedClick >= 1200)
                {
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[도전 안전확인] 선택됨 확인 -> 카드 안 선택됨만 1회 클릭하여 도전으로 전환 @ {selected.Center}");
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

            // Challenge without the right entry word is not ready yet. Never click challenge.
            if (challenge.Found)
            {
                long now = Environment.TickCount64;
                if (now - lastStateLog >= 1200)
                {
                    Log?.Invoke("[도전 안전확인] 도전은 확인됐지만 오른쪽 입장하기 미확인 -> 도전은 누르지 않고 대기");
                    lastStateLog = now;
                }
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            // Entry text alone is not enough to authorize Space. Also do not let retry logic
            // run on an entry-like screen; wait for the exact state word to settle.
            if (enter.Found)
            {
                long now = Environment.TickCount64;
                if (now - lastStateLog >= 1200)
                {
                    Log?.Invoke($"[도전 안전확인] 오른쪽 입장하기는 보이지만 도전/선택됨 상태 미확인 -> 입력 없이 재확인 @ {enter.Bounds}");
                    lastStateLog = now;
                }
                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            // Normal result/retry fast path. Exact OCR only, and only after all entry-state
            // signals above are absent. This prevents the party-search / entry area from
            // ever being treated as a retry control.
            var normalRetry = await _detector.DetectAsync("retry_ocr_strict", frame, ct);
            if (normalRetry.Found)
            {
                Log?.Invoke($"[던전 결과] 정확 OCR 다시 하기 감지 1/2 OCR={normalRetry.ReadText} bounds={normalRetry.Bounds}");
                await Task.Delay(220, ct);

                using var retryConfirmFrame = await CaptureGameWindowAsync(ct);

                var guardSelected = await _detector.DetectAsync("selected_ocr_strict", retryConfirmFrame, ct);
                var guardChallenge = await _detector.DetectAsync("challenge_confirm_strict", retryConfirmFrame, ct);
                var guardEnter = await _detector.DetectAsync("enter_bottom", retryConfirmFrame, ct);
                if (guardSelected.Found || guardChallenge.Found || guardEnter.Found)
                {
                    Log?.Invoke(
                        $"[던전 결과] 입장 화면 신호 재확인 -> 다시 하기 클릭 금지 " +
                        $"selected={(guardSelected.Found ? 1 : 0)} " +
                        $"challenge={(guardChallenge.Found ? 1 : 0)} " +
                        $"enter={(guardEnter.Found ? 1 : 0)}");
                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                var retryConfirm = await _detector.DetectAsync("retry_ocr_strict", retryConfirmFrame, ct);
                if (!retryConfirm.Found)
                {
                    Log?.Invoke("[던전 결과] 정확 OCR 다시 하기 2/2 확인 실패 -> 클릭 안 함");
                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                Log?.Invoke($"[던전 결과] 정확 OCR 다시 하기 2/2 연속 확인 OCR={retryConfirm.ReadText} bounds={retryConfirm.Bounds}");

                if (normalResultRetryClicks >= 2)
                {
                    Log?.Invoke("[던전 결과] 정상 다시 하기 클릭 2회 소진 -> 기존 타임아웃/자동복구에 맡김");
                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                normalResultRetryClicks++;
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[던전 결과] 정상 다시 하기 클릭 {normalResultRetryClicks}/2 @ {retryConfirm.Center}");
                _input.ClickClientPoint(_hwnd, retryConfirm.Center);
                await Task.Delay(Math.Max(900, _settings.ClickSettleMs), ct);

                using var afterRetryFrame = await CaptureGameWindowAsync(ct);
                var stillRetry = await _detector.DetectAsync("retry_ocr_strict", afterRetryFrame, ct);
                if (!stillRetry.Found)
                {
                    timer.Restart();
                    lastSelectedClick = 0;
                    Log?.Invoke("[던전 결과] 다시 하기 화면 이탈 확인 -> 45초 검증 타이머 재시작");
                }
                else
                {
                    Log?.Invoke("[던전 결과] 다시 하기 클릭 후 화면 유지 -> 재확인 (임의 좌표 클릭 없음)");
                }

                await Task.Delay(ConfirmIntervalMs, ct);
                continue;
            }

            long unknownNow = Environment.TickCount64;
            if (unknownNow - lastStateLog >= 1500)
            {
                Log?.Invoke("[도전 안전확인] 현재 입장 상태 미확인 -> 클릭 없이 재확인");
                lastStateLog = unknownNow;
            }

            await Task.Delay(ConfirmIntervalMs, ct);
        }

        throw new TimeoutException(
            "45초 동안 현재 도전+입장하기 또는 선택됨->도전 상태를 안정적으로 확인하지 못했습니다.");
    }

'''

engine = engine[:start] + new_guard + engine[end:]
write(engine_path, engine)

# Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.47", "V0.1.48")
                   .replace("0.1.47.0", "0.1.48.0")
                   .replace("0.1.47", "0.1.48"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.48_CURRENT_CHALLENGE_DIRECT_ENTRY.txt").write_text(
    "MABI AUTO V0.1.48 - CURRENT CHALLENGE DIRECT ENTRY\n\n"
    "Fixes the V0.1.47 case where the game is already on the exact challenge state with the exact right-bottom entry control visible, but the verifier still waits for a previous selected-state transition.\n"
    "Current exact challenge + exact right-bottom entry now wins immediately and authorizes the existing Space-only entry path after two confirming frames.\n"
    "A previous selected observation is no longer required.\n"
    "Exact selected is still clicked only inside the dungeon-card safe rectangle to change it to challenge.\n"
    "Challenge itself is never clicked.\n"
    "Entry still uses Space only; the party-search button is not clicked.\n"
    "Strict retry OCR runs only when selected/challenge/entry signals are all absent, with a second entry-state guard before retry click.\n",
    encoding="utf-8"
)

check = read(engine_path)
required = (
    "DUNGEON_CURRENT_CHALLENGE_DIRECT_ENTRY_V9",
    "현재 화면이 이미 도전 상태 -> 선택됨 이력 없이 바로 입장 허용",
    'DetectAsync("challenge_confirm_strict", frame, ct)',
    'DetectAsync("enter_bottom", frame, ct)',
    'DetectAsync("selected_ocr_strict", frame, ct)',
    'DetectAsync("retry_ocr_strict", frame, ct)',
    "선택됨 확인 -> 카드 안 선택됨만 1회 클릭하여 도전으로 전환",
    "도전은 누르지 않고 대기",
    "입장 화면 신호 재확인 -> 다시 하기 클릭 금지",
)
for marker in required:
    if marker not in check:
        raise RuntimeError("V0.1.48 marker missing: " + marker)

start = check.index("private async Task VerifyChallengeBeforeEntryAsync")
end = check.index("private async Task<bool> VerifyAbyssSelectionScreenAsync", start)
block = check[start:end]
for forbidden in (
    'DetectAsync("retry", frame, ct)',
    'DetectAsync("selected_red_visual", frame, ct)',
    'DetectAsync("challenge_visual", frame, ct)',
    "CheckMonitorsAsync(frame, ct)",
):
    if forbidden in block:
        raise RuntimeError("forbidden verifier behavior remains: " + forbidden)

if "_input.TapScanCode(0x39);" not in check:
    raise RuntimeError("Space-only entry path missing")
if "[retry guard] 입장 화면에서는 다시 하기 클릭 금지" not in check:
    raise RuntimeError("normal retry entry guard missing")
if "[던전 자동복구] 입장 화면 우선 판정" not in check:
    raise RuntimeError("V0.1.47 recovery entry priority missing")

print("V0.1.48 patch applied: current challenge + exact entry bypasses selected-history requirement")
