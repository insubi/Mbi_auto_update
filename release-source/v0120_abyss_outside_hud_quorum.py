#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0120_abyss_outside_hud_quorum.py SOURCE_ROOT")

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
        raise RuntimeError(f"V0.1.20 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


engine = read(engine_path)

# Throttle detailed HUD-score diagnostics so a failed outside check does not flood logs.
engine = replace_once(
    engine,
    "    private int _cycle;\n",
    "    private int _cycle;\n    private long _lastAbyssOutsideHudScoreLog;\n",
    "outside HUD score-log field",
)

old_detect = '''    private async Task<bool> DetectAbyssOutsideWorkflowAsync(Bitmap frame, CancellationToken ct)
    {
        var home = await _detector.DetectAsync("abyss_outside_home_key", frame, ct);
        if (!home.Found) return false;
        var end = await _detector.DetectAsync("abyss_outside_end_key", frame, ct);
        if (!end.Found) return false;
        var kHud = await _detector.DetectAsync("abyss_outside_k_hud", frame, ct);
        if (!kHud.Found) return false;
        var iHud = await _detector.DetectAsync("abyss_outside_i_hud", frame, ct);
        if (!iHud.Found) return false;

        // A result overlay is explicit dungeon-internal evidence; never accept outside in that state.
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        if (clearTitle.Found) return false;
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        return !touch.Found;
    }
'''

new_detect = '''    private async Task<bool> DetectAbyssOutsideWorkflowAsync(Bitmap frame, CancellationToken ct)
    {
        var home = await _detector.DetectAsync("abyss_outside_home_key", frame, ct);
        var end = await _detector.DetectAsync("abyss_outside_end_key", frame, ct);
        var kHud = await _detector.DetectAsync("abyss_outside_k_hud", frame, ct);
        var iHud = await _detector.DetectAsync("abyss_outside_i_hud", frame, ct);

        int matched =
            (home.Found ? 1 : 0) +
            (end.Found ? 1 : 0) +
            (kHud.Found ? 1 : 0) +
            (iHud.Found ? 1 : 0);

        long now = Environment.TickCount64;
        bool scoreLogDue = _lastAbyssOutsideHudScoreLog == 0 || now - _lastAbyssOutsideHudScoreLog >= 2000;

        if (matched < 3)
        {
            if (scoreLogDue)
            {
                Log?.Invoke(
                    $"[어비스] 던전 밖 HUD 점수 Home={home.Score:0.000} End={end.Score:0.000} K={kHud.Score:0.000} I={iHud.Score:0.000} / 인식={matched}/4 -> 3개 미만");
                _lastAbyssOutsideHudScoreLog = now;
            }
            return false;
        }

        // Three of four fixed outside HUD markers are enough. A clear/result overlay is still
        // explicit dungeon-internal evidence and blocks outside acceptance.
        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);
        var touch = await _detector.DetectAsync("abyss_touch_screen", frame, ct);
        bool outside = !clearTitle.Found && !touch.Found;

        if (outside || scoreLogDue)
        {
            Log?.Invoke(
                $"[어비스] 던전 밖 HUD 점수 Home={home.Score:0.000} End={end.Score:0.000} K={kHud.Score:0.000} I={iHud.Score:0.000} / 인식={matched}/4 / Clear={(clearTitle.Found ? 1 : 0)} Touch={(touch.Found ? 1 : 0)} -> {(outside ? "밖 인정" : "클리어 화면으로 보류")}");
            _lastAbyssOutsideHudScoreLog = now;
        }

        return outside;
    }
'''
engine = replace_once(engine, old_detect, new_detect, "outside HUD detector")

old_recovery = '''            if (await DetectAbyssOutsideWorkflowAsync(frame, ct))
            {
                outsideConsecutive++;
                Log?.Invoke($"[어비스 자동복구] 던전 밖 HUD 확인 {outsideConsecutive}/3");
                if (outsideConsecutive >= 3)
                {
                    Log?.Invoke("[어비스 자동복구] 던전 밖 HUD 3회 연속 확인 완료 -> 처음부터 재시작");
                    return true;
                }
                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                continue;
            }
            outsideConsecutive = 0;
'''

new_recovery = '''            if (await DetectAbyssOutsideWorkflowAsync(frame, ct))
            {
                Log?.Invoke("[어비스 자동복구] 던전 밖 HUD 3/4 이상 확인 -> 복구 즉시 완료, 처음부터 재시작");
                return true;
            }
            outsideConsecutive = 0;
'''
engine = replace_once(engine, old_recovery, new_recovery, "Smart Recovery immediate outside success")

engine = replace_once(
    engine,
    'Log?.Invoke($"[어비스] 던전 밖 HUD 확인 {outsideConsecutive}/3");',
    'Log?.Invoke($"[어비스] 던전 밖 HUD 3/4 이상 확인 {outsideConsecutive}/3");',
    "normal-exit quorum log",
)
engine = replace_once(
    engine,
    'throw new TimeoutException("나가기 후 60초 안에 던전 밖 고정 HUD(Home+End+K+I)를 확인하지 못했습니다.");',
    'throw new TimeoutException("나가기 후 60초 안에 던전 밖 고정 HUD 4개 중 3개 이상을 확인하지 못했습니다.");',
    "normal-exit timeout message",
)

required = [
    "_lastAbyssOutsideHudScoreLog",
    "int matched =",
    "matched < 3",
    "던전 밖 HUD 점수 Home=",
    "인식={matched}/4",
    "던전 밖 HUD 3/4 이상 확인 -> 복구 즉시 완료",
    "던전 밖 HUD 3/4 이상 확인 {outsideConsecutive}/3",
    "고정 HUD 4개 중 3개 이상",
    "VerifyAbyssSelectionScreenAsync",
    "어비스 클릭 검증 실패",
]
for marker in required:
    if marker not in engine:
        raise RuntimeError(f"required V0.1.20 marker missing: {marker}")

write(engine_path, engine)

# Runtime version bump. Do not rewrite historical .txt changelogs.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (
        text.replace("V0.1.19", "V0.1.20")
        .replace("0.1.19.0", "0.1.20.0")
        .replace("0.1.19", "0.1.20")
    )
    if changed != text:
        write(path, changed)

changes = root / "CHANGES_V0.1.20_ABYSS_OUTSIDE_HUD_QUORUM.txt"
changes.write_text(
    "MABI AUTO V0.1.20 - ABYSS OUTSIDE HUD QUORUM\n"
    "\n"
    "Base: V0.1.19.\n"
    "Abyss outside-state detection now accepts any 3 of Home/End/K/I instead of requiring all 4.\n"
    "Dungeon-clear/touch result screens still block outside-state acceptance.\n"
    "HUD template scores are logged for Home, End, K and I; failed checks are throttled to about once every 2 seconds.\n"
    "During Smart Recovery, a valid 3-of-4 outside state completes recovery immediately and restarts from step 1.\n"
    "Normal exit still requires 3 consecutive outside confirmations, but each confirmation now uses the 3-of-4 quorum.\n"
    "V0.1.19 Abyss menu misclick guard and V0.1.18 fishing behavior are preserved.\n",
    encoding="utf-8",
)

print("V0.1.20 applied: Abyss outside HUD 3-of-4 quorum + score logging + immediate Smart Recovery success")
