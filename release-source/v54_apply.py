#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"v54 pattern missing ({label}) in {path}")
    write(path, text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Version bump: v53 -> v54
# ---------------------------------------------------------------------------
p = app / "UpdateManager.cs"
s = read(p)
if 'public const string CurrentVersion = "v53";' not in s:
    raise RuntimeError("v53 UpdateManager version not found")
write(p, s.replace('public const string CurrentVersion = "v53";', 'public const string CurrentVersion = "v54";', 1))

p = app / "MainForm.Dashboard.cs"
s = read(p)
s = s.replace('Text = "v53.0.0"', 'Text = "v54.0.0"')
s = s.replace('Dashboard v53', 'Dashboard v54')
s = s.replace('v53  |  Mabi Auto', 'v54  |  Mabi Auto')
write(p, s)

p = app / "MainForm.ReferenceUI.cs"
s = read(p)
s = s.replace('v53.0.0 · UI', 'v54.0.0 · UI')
write(p, s)

p = app / "FishingAutomation.csproj"
s = read(p)
for key, value in {
    "Version": "54.0.0",
    "AssemblyVersion": "54.0.0.0",
    "FileVersion": "54.0.0.0",
}.items():
    pattern = rf'<{key}>[^<]+</{key}>'
    if not re.search(pattern, s):
        raise RuntimeError(f"v54 project version tag missing: {key}")
    s = re.sub(pattern, f'<{key}>{value}</{key}>', s, count=1)
write(p, s)


# ---------------------------------------------------------------------------
# Abyss clear-screen recognition helpers.
# 1) Detect either '던전 클리어' or the large S grade in the clear screen.
# 2) Existing abyss_touch_screen remains the fallback and verification target.
# ---------------------------------------------------------------------------
targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(read(targets_path))

new_targets = {
    "abyss_dungeon_clear_text": {
        "Id": "abyss_dungeon_clear_text",
        "Kind": "ocr",
        "Text": "던전 클리어",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
        "Roi": {"X": 80, "Y": 300, "Width": 640, "Height": 520},
    },
    "abyss_clear_grade_s": {
        "Id": "abyss_clear_grade_s",
        "Kind": "ocr",
        "Text": "S",
        "MaxEditDistance": 0,
        "OcrRetryAt2x": True,
        "Roi": {"X": 230, "Y": 100, "Width": 340, "Height": 430},
    },
}

for tid, entry in new_targets.items():
    existing = next((t for t in targets if t.get("Id") == tid), None)
    if existing is None:
        targets.append(entry)
    else:
        existing.clear()
        existing.update(entry)

write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Scenario engine clear handling.
# First click: dungeon-clear text OR large S OR existing touch-screen prompt.
# After the first click, if '화면을 터치해 주세요' is still present, click once more.
# Never proceed to abyss_leave_dungeon while the touch prompt is still visible.
# ---------------------------------------------------------------------------
engine = app / "Dungeon" / "ScenarioEngine.cs"
s = read(engine)

old_detect = '''            if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
            {
                found = await _detector.DetectAsync(step.Target, frame, ct);
                if (!found.Found && await CheckMonitorsAsync(frame, ct))
                    continue;
            }'''
new_detect = '''            if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
            {
                // Clear screen can appear before the touch prompt is reliably recognized.
                // Prefer the clear title / large S grade, then fall back to the existing
                // "화면을 터치해 주세요" target.
                found = await _detector.DetectAsync("abyss_dungeon_clear_text", frame, ct);
                if (!found.Found)
                    found = await _detector.DetectAsync("abyss_clear_grade_s", frame, ct);
                if (!found.Found)
                    found = await _detector.DetectAsync(step.Target, frame, ct);

                if (!found.Found && await CheckMonitorsAsync(frame, ct))
                    continue;
            }'''
if old_detect not in s:
    raise RuntimeError("v54 Abyss clear detection block not found")
s = s.replace(old_detect, new_detect, 1)

old_click = '''                    _input.ClickClientPoint(_hwnd, found.Center);
                    await Task.Delay(_settings.ClickSettleMs, ct);

                    if (step.Target.Equals("abyss_exit", StringComparison.OrdinalIgnoreCase))
                        await WaitForAbyssHomeAfterNormalExitAsync(ct);'''
new_click = '''                    if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))
                    {
                        await AdvanceAbyssClearScreenAsync(found, ct);
                    }
                    else
                    {
                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(_settings.ClickSettleMs, ct);
                    }

                    if (step.Target.Equals("abyss_exit", StringComparison.OrdinalIgnoreCase))
                        await WaitForAbyssHomeAfterNormalExitAsync(ct);'''
if old_click not in s:
    raise RuntimeError("v54 ScenarioEngine click block not found")
s = s.replace(old_click, new_click, 1)

helper_marker = '''    private async Task WaitForAbyssHomeAfterNormalExitAsync(CancellationToken ct)
'''
helper = '''    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)
    {
        Log?.Invoke("[어비스] 클리어 화면 감지 -> 1차 클릭");
        _input.ClickClientPoint(_hwnd, firstDetection.Center);
        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);

        using (var afterFirst = await CaptureGameWindowAsync(ct))
        {
            var touchStillVisible = await _detector.DetectAsync("abyss_touch_screen", afterFirst, ct);
            if (!touchStillVisible.Found)
            {
                Log?.Invoke("[어비스] 1차 클릭 후 클리어 화면 전환 확인");
                return;
            }

            Log?.Invoke("[어비스] '화면을 터치해 주세요' 유지 -> 2차 클릭");
            _input.ClickClientPoint(_hwnd, touchStillVisible.Center);
        }

        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);

        using var afterSecond = await CaptureGameWindowAsync(ct);
        var touchAfterSecond = await _detector.DetectAsync("abyss_touch_screen", afterSecond, ct);
        if (touchAfterSecond.Found)
        {
            Log?.Invoke("[어비스] 경고: 2회 클릭 후에도 '화면을 터치해 주세요'가 남아 있음");
            throw new TimeoutException("어비스 클리어 화면이 2회 클릭 후에도 넘어가지 않았습니다.");
        }

        Log?.Invoke("[어비스] 2차 클릭 후 클리어 화면 전환 확인");
    }

'''
if helper_marker not in s:
    raise RuntimeError("v54 helper insertion marker not found")
s = s.replace(helper_marker, helper + helper_marker, 1)
write(engine, s)


(root / "CHANGES_v54_ABYSS_CLEAR_DOUBLE_CLICK.txt").write_text(
    "Mabi_Auto v54\n"
    "- Abyss clear step first detects '던전 클리어' or the large S grade.\n"
    "- First clear detection triggers one click.\n"
    "- After 1 second, if '화면을 터치해 주세요' is still visible, one additional click is sent.\n"
    "- Maximum clear-screen clicks per detection are two.\n"
    "- If the touch prompt remains after the second click, the macro reports the clear-screen failure immediately instead of waiting 60 seconds for abyss_leave_dungeon.\n"
    "- Existing Fishing, Dungeon, Abyss selection and v53 UI behavior are otherwise unchanged.\n",
    encoding="utf-8",
)

print("v54 Abyss clear-screen double-click flow applied")
