#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0133_result_retry_fastpath.py SOURCE_ROOT")

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
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)

engine = read(engine_path)
method_start = engine.index("    private async Task VerifyChallengeBeforeEntryAsync(CancellationToken ct)")
method_end = engine.index("    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)", method_start)
method = engine[method_start:method_end]

old_locals = '''        int challengeConsecutive = 0;
        long lastSelectedClick = 0;
        long lastAmbiguousLog = 0;
        var timer = Stopwatch.StartNew();
'''
new_locals = '''        int challengeConsecutive = 0;
        long lastSelectedClick = 0;
        long lastAmbiguousLog = 0;
        int normalResultRetryClicks = 0;
        var timer = Stopwatch.StartNew();
'''
method = replace_once(method, old_locals, new_locals, "entry verifier locals")

old_loop = '''            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            if (await CheckMonitorsAsync(frame, ct))
'''
new_loop = '''            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);

            // DUNGEON_RESULT_RETRY_FASTPATH_V8
            // A normal dungeon clear can leave us on the reward/result screen while this
            // verifier is waiting for selected -> challenge -> enter. Handle the existing
            // hybrid "retry" target here before the 45-second timeout so a normal clear does
            // not become a generic auto-recovery alert. Never use a fallback coordinate.
            var normalRetry = await _detector.DetectAsync("retry", frame, ct);
            if (normalRetry.Found)
            {
                challengeConsecutive = 0;
                Log?.Invoke($"[던전 결과] 다시 하기 감지 1/2 score={normalRetry.Score:0.000}");
                await Task.Delay(220, ct);

                using var retryConfirmFrame = await CaptureGameWindowAsync(ct);
                var retryConfirm = await _detector.DetectAsync("retry", retryConfirmFrame, ct);
                if (retryConfirm.Found)
                {
                    Log?.Invoke($"[던전 결과] 다시 하기 2/2 연속 확인 score={retryConfirm.Score:0.000}");

                    if (normalResultRetryClicks >= 2)
                    {
                        Log?.Invoke("[던전 결과] 정상 다시 하기 클릭 2회 소진 -> 기존 45초 타임아웃/자동복구에 맡김");
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
                    var stillRetry = await _detector.DetectAsync("retry", afterRetryFrame, ct);
                    if (!stillRetry.Found)
                    {
                        timer.Restart();
                        lastSelectedClick = 0;
                        Log?.Invoke("[던전 결과] 다시 하기 화면 이탈 확인 -> 정상 진행, 45초 검증 타이머 재시작");
                    }
                    else
                    {
                        Log?.Invoke("[던전 결과] 다시 하기 클릭 후 화면 유지 -> 재확인 (임의 좌표 클릭 없음)");
                    }

                    await Task.Delay(ConfirmIntervalMs, ct);
                    continue;
                }

                Log?.Invoke("[던전 결과] 다시 하기 2/2 확인 실패 -> 클릭 안 함");
            }

            if (await CheckMonitorsAsync(frame, ct))
'''
method = replace_once(method, old_loop, new_loop, "entry verifier result fast path")
engine = engine[:method_start] + method + engine[method_end:]
write(engine_path, engine)

for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.32", "V0.1.33")
                   .replace("0.1.32.0", "0.1.33.0")
                   .replace("0.1.32", "0.1.33"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.33_RESULT_RETRY_FASTPATH.txt").write_text(
    "MABI AUTO V0.1.33 - RESULT RETRY FAST PATH\n\n"
    "A normal dungeon result/reward screen is now handled inside the selected/challenge/entry verification loop before its 45-second timeout.\n"
    "The existing hybrid 'retry' target must be confirmed on two frames before clicking its detected center. No fallback coordinate is used.\n"
    "After the retry screen disappears, the selected/challenge/entry verification timer is restarted so the next run receives a fresh 45-second window.\n"
    "At most two normal retry clicks are attempted per verification call; if the screen does not transition, the existing timeout and auto-recovery remain the fallback.\n"
    "The V0.1.32 Ula fixed-click/map-transition fix, Peaca D1-1/D2-1 route, dungeon semantics, Abyss, fishing, F10, retry target, scene-skip behavior, and policy/ERROR88 removal are preserved.\n",
    encoding="utf-8"
)

check = read(engine_path)
for required in (
    "DUNGEON_RESULT_RETRY_FASTPATH_V8",
    'var normalRetry = await _detector.DetectAsync("retry", frame, ct);',
    "다시 하기 감지 1/2",
    "다시 하기 2/2 연속 확인",
    "45초 검증 타이머 재시작",
    "normalResultRetryClicks >= 2",
    "timer.Restart();",
    "DUNGEON_CHALLENGE_DISAMBIGUATION_V5",
    "45초 동안 선택됨 -> 도전 -> 입장하기 상태를 안정적으로 확인하지 못했습니다.",
    "var ullaBreadcrumbPoint = new Point(82, 66);",
    "peaca_d1_1",
    "peaca_d2_1",
):
    if required not in check:
        raise RuntimeError(f"V0.1.33 required marker missing: {required}")

for forbidden in (
    "peaca_d2_2",
    "route_d2_2",
    "route_enter_d2_2",
    "DUNGEON_POLICY_SHUTDOWN_DETECTED",
    "ThrowIfDungeonPolicyShutdownAsync",
):
    if forbidden in check:
        raise RuntimeError(f"forbidden regression returned: {forbidden}")

print("V0.1.33 patch applied: normal result/retry fast path before 45-second recovery timeout")
