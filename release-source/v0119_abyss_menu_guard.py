#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0119_abyss_menu_guard.py SOURCE_ROOT")

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
        raise RuntimeError(f"expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


engine = read(engine_path)

helper_marker = "    private async Task ExecuteStepAsync(ScenarioStep step, CancellationToken ct)\n"
helper = '''    private async Task<bool> VerifyAbyssSelectionScreenAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        int consecutive = 0;
        string[] ids =
        {
            "abyss_dungeon_hallucination_anchorage",
            "abyss_dungeon_madness_cave",
            "abyss_dungeon_scattered_waterway"
        };

        while (sw.Elapsed < TimeSpan.FromSeconds(6))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            bool foundAny = false;
            string foundId = "";

            foreach (string id in ids)
            {
                var r = await _detector.DetectAsync(id, frame, ct);
                if (!r.Found) continue;
                foundAny = true;
                foundId = id;
                break;
            }

            if (foundAny)
            {
                consecutive++;
                Log?.Invoke($"[어비스] 어비스 던전 선택 화면 확인 {consecutive}/2 ({foundId})");
                if (consecutive >= 2)
                    return true;
            }
            else
            {
                consecutive = 0;
            }

            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        return false;
    }

'''
engine = replace_once(
    engine,
    helper_marker,
    helper + helper_marker,
    "Abyss selection verification helper insertion",
)

engine = replace_once(
    engine,
    '''        bool alternativeClicked = false;
        int abyssClearConsecutive = 0;
''',
    '''        bool alternativeClicked = false;
        int abyssClearConsecutive = 0;
        var abyssIconRejected = new List<Rectangle>();
''',
    "Abyss icon rejected-candidate state",
)

engine = replace_once(
    engine,
    '''            else
            {
                if (await CheckMonitorsAsync(frame, ct))
                    continue;
                found = await _detector.DetectAsync(step.Target, frame, ct);
            }
''',
    '''            else
            {
                if (await CheckMonitorsAsync(frame, ct))
                    continue;

                if (step.Target.Equals("abyss_icon", StringComparison.OrdinalIgnoreCase) && abyssIconRejected.Count > 0)
                {
                    using var masked = (Bitmap)frame.Clone();
                    using (var g = Graphics.FromImage(masked))
                    {
                        foreach (var rejected in abyssIconRejected)
                            g.FillRectangle(Brushes.Black, rejected);
                    }
                    found = await _detector.DetectAsync(step.Target, masked, ct);
                }
                else
                {
                    found = await _detector.DetectAsync(step.Target, frame, ct);
                }
            }
''',
    "Abyss icon rejected-candidate masking",
)

engine = replace_once(
    engine,
    '''                    if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
                    {
                        await AdvanceAbyssClearScreenAsync(found, ct);
                    }
                    else
                    {
                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(_settings.ClickSettleMs, ct);
                    }
''',
    '''                    if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
                    {
                        await AdvanceAbyssClearScreenAsync(found, ct);
                    }
                    else if (step.Target.Equals("abyss_icon", StringComparison.OrdinalIgnoreCase))
                    {
                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

                        if (!await VerifyAbyssSelectionScreenAsync(ct))
                        {
                            var rejected = found.Bounds;
                            rejected.Inflate(24, 24);
                            abyssIconRejected.Add(rejected);
                            Log?.Invoke($"[어비스] 어비스 클릭 검증 실패 {abyssIconRejected.Count}/4 @ {found.Bounds} score={found.Score:0.000} -> ESC 후 해당 후보 제외");

                            _hwnd = await ResolveRequiredGameWindowAsync(ct);
                            NativeMethods.SetForegroundWindow(_hwnd);
                            _input.TapScanCode(0x01); // ESC: wrong content -> menu
                            await Task.Delay(900, ct);

                            if (abyssIconRejected.Count >= 4)
                            {
                                // Close the menu as well so Smart Recovery sees the outside HUD immediately.
                                _input.TapScanCode(0x01);
                                await Task.Delay(700, ct);
                                throw new TimeoutException("어비스 아이콘 후보 4개를 클릭 검증했지만 어비스 던전 선택 화면이 확인되지 않았습니다.");
                            }

                            continue;
                        }

                        Log?.Invoke($"[어비스] 어비스 클릭 검증 성공 @ {found.Bounds} score={found.Score:0.000}");
                    }
                    else
                    {
                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(_settings.ClickSettleMs, ct);
                    }
''',
    "Abyss icon post-click verification",
)

required = [
    "VerifyAbyssSelectionScreenAsync",
    "abyssIconRejected = new List<Rectangle>()",
    "g.FillRectangle(Brushes.Black, rejected)",
    "어비스 클릭 검증 실패",
    "_input.TapScanCode(0x01); // ESC: wrong content -> menu",
    "어비스 아이콘 후보 4개",
    "어비스 클릭 검증 성공",
]
for marker in required:
    if marker not in engine:
        raise RuntimeError(f"required V0.1.19 marker missing: {marker}")

write(engine_path, engine)

# Runtime version bump. Keep historical changelog text untouched.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (
        text.replace("V0.1.18", "V0.1.19")
        .replace("0.1.18.0", "0.1.19.0")
        .replace("0.1.18", "0.1.19")
    )
    if changed != text:
        write(path, changed)

# Verify the target still uses the original recognition image/threshold.
targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(read(targets_path))
abyss_target = next((t for t in targets if t.get("Id") == "abyss_icon"), None)
if not abyss_target or float(abyss_target.get("Threshold", -1)) != 0.8:
    raise RuntimeError("abyss_icon target/threshold changed unexpectedly")

changes = root / "CHANGES_V0.1.19_ABYSS_MENU_GUARD.txt"
changes.write_text(
    "MABI AUTO V0.1.19 - ABYSS MENU MISCLICK GUARD\n"
    "\n"
    "Base: V0.1.18.\n"
    "Root cause: abyss_icon used a full-window grayscale best-match and the step returned immediately after any accepted click.\n"
    "Fix: every Abyss icon click is verified by known Abyss dungeon-selection templates for two consecutive frames.\n"
    "If verification fails, ESC returns to the menu, the false-positive rectangle is excluded, and the next-best candidate is tried.\n"
    "After four rejected candidates, the menu is closed and Smart Recovery is triggered immediately.\n"
    "Abyss recognition template bytes/threshold and fishing V0.1.18 behavior are preserved.\n",
    encoding="utf-8",
)

print("V0.1.19 applied: Abyss click verify -> ESC on wrong content -> reject candidate -> retry")
