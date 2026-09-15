#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v81_apply.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = read(path)
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != 1:
        raise RuntimeError(f"V0.1.8 expected exactly one {label}, found {count}")
    write(path, text.replace(old, new, 1))


base_audit_path = root / "V0_1_7_FISHING_CAPTURE_RESYNC_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1.7 audit missing; v81 must be applied to V0.1.7/v80 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.7":
    raise RuntimeError("unexpected public base version for v81")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.7";',
             'public const string CurrentVersion = "V0.1.8";',
             "UpdateManager version")
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.7</Version>", "<Version>0.1.8</Version>", "project Version")
replace_once(project, "<AssemblyVersion>0.1.7.0</AssemblyVersion>", "<AssemblyVersion>0.1.8.0</AssemblyVersion>", "project AssemblyVersion")
replace_once(project, "<FileVersion>0.1.7.0</FileVersion>", "<FileVersion>0.1.8.0</FileVersion>", "project FileVersion")

# Real 22:55 debug frame (800x999) contains the Space hook clearly, but the
# canonical hook template peaks around 0.766 at scale ~1.10. 0.78 therefore
# rejects a genuine hook. Lower only the audited hook acceptance to 0.72 while
# strengthening temporal confirmation from 2 to 3 frames.
bot_path = app / "FishingBot.cs"
bot = read(bot_path)
old_threshold = 'Math.Min(_cfg.HookThreshold, 0.78)'
threshold_count = bot.count(old_threshold)
if threshold_count < 3:
    raise RuntimeError(f"V0.1.8 expected at least three V0.1.7 hook threshold checks, found {threshold_count}")
bot = bot.replace(old_threshold, 'Math.Min(_cfg.HookThreshold, 0.72)')

pattern = re.compile(r'if\s*\(\s*hookFrames\s*>=\s*2\s*\)')
confirm_count = len(pattern.findall(bot))
if confirm_count < 1:
    raise RuntimeError("V0.1.8 could not find hookFrames >= 2 confirmation")
bot = pattern.sub('if (hookFrames >= 3)', bot)
write(bot_path, bot)

config_path = app / "config.json"
replace_once(config_path, '"HookThreshold": 0.78', '"HookThreshold": 0.72', "HookThreshold")

# Narrow the fallback search around the actual fixed HUD position. V0.1.7 used
# 18%-82% width and bottom 32%, which was intentionally broad for coordinate
# recovery. With the threshold now lower, keep the recovery ROI conservative to
# avoid matching unrelated lower-screen UI.
matcher_path = app / "TemplateMatcher.cs"
matcher = read(matcher_path)
old_roi = '''        int left = Math.Max(0, (int)Math.Round(gray.Width * 0.18));
        int top = Math.Max(0, (int)Math.Round(gray.Height * 0.68));
        int width = Math.Max(1, gray.Width - (left * 2));
        int height = Math.Max(1, gray.Height - top);
        Rectangle recoveryRoi = new(left, top, width, height);'''
new_roi = '''        int left = Math.Max(0, (int)Math.Round(gray.Width * 0.28));
        int right = Math.Min(gray.Width, (int)Math.Round(gray.Width * 0.72));
        int top = Math.Max(0, (int)Math.Round(gray.Height * 0.72));
        int bottom = Math.Min(gray.Height, (int)Math.Round(gray.Height * 0.97));
        int width = Math.Max(1, right - left);
        int height = Math.Max(1, bottom - top);
        Rectangle recoveryRoi = new(left, top, width, height);'''
if matcher.count(old_roi) != 1:
    raise RuntimeError(f"V0.1.8 expected one V0.1.7 recovery ROI block, found {matcher.count(old_roi)}")
matcher = matcher.replace(old_roi, new_roi, 1)
if matcher.count('if (primary.Score >= 0.78) return primary;') != 1:
    raise RuntimeError("V0.1.8 could not update MatchHook primary threshold")
matcher = matcher.replace('if (primary.Score >= 0.78) return primary;', 'if (primary.Score >= 0.72) return primary;', 1)
write(matcher_path, matcher)

for marker in (
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도',
):
    if marker not in bot:
        raise RuntimeError(f"V0.1.8 requires retained fishing invariant: {marker}")

capture_path = app / "CaptureService.cs"
capture = read(capture_path)
for marker in (
    'NativeMethods.GetClientRect(window.Handle, out var liveClient)',
    'NativeMethods.ClientToScreen(window.Handle, ref liveOrigin)',
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);',
):
    if marker not in capture:
        raise RuntimeError(f"V0.1.8 requires V0.1.7 capture invariant: {marker}")

start_path = root / "START.cmd"
start = read(start_path)
if 'copy /y "%ROOT%\\FishingAutomation\\templates\\hook.png" "%ROOT%\\release\\templates\\hook.png"' not in start:
    raise RuntimeError("V0.1.8 requires V0.1.7 runtime hook refresh")

changes = root / "CHANGES_V0.1.8_REAL_DEBUG_HOOK.txt"
changes.write_text(
    "MABI AUTO V0.1.8 - real debug-frame hook recognition fix\n"
    "- The user-supplied 22:55 stage1_hook_wait_8s frame is a true 800x999 game-client capture and visibly contains the Space fishing hook.\n"
    "- Offline OpenCV comparison against the packaged 54x54 hook template peaks near 0.766 at scale about 1.10, proving the V0.1.7 0.78 cutoff can reject a genuine hook even when capture coordinates are correct.\n"
    "- Effective hook acceptance is 0.72, but temporal confirmation is strengthened from 2 to 3 consecutive frames.\n"
    "- The fallback hook search is narrowed to the center 28%-72% width and 72%-97% height to reduce false positives at the lower threshold.\n"
    "- V0.1.7 live ClientToScreen capture-origin refresh, foreground recovery, stale hook self-heal, and 8-second debug capture remain enabled.\n"
    "- V0.1.5 live-gauge stage resync and truthful Space input retry remain enabled.\n",
    encoding="utf-8",
)

tracked = [
    app / "UpdateManager.cs",
    project,
    bot_path,
    config_path,
    matcher_path,
    capture_path,
    app / "FishingFocusGuard.cs",
    app / "NativeMethods.cs",
    app / "MainForm.cs",
    start_path,
    changes,
]
audit = {
    "base_public_version": "V0.1.7",
    "technical_bridge_base": "v80",
    "technical_bridge_tag": "v81",
    "version": "V0.1.8",
    "purpose": "Accept the real Space hook seen in the 22:55 debug frame without broadening false-positive exposure",
    "real_debug_frame": "20260915_225532_757_stage1_hook_wait_8s.png",
    "measured_template_peak": 0.766,
    "measured_scale": 1.10,
    "effective_hook_threshold": 0.72,
    "hook_confirm_frames": 3,
    "hook_recovery_roi": "center 28%-72% width, 72%-97% height",
    "hook_template_sha256": "b85d3443d156ec31957a7b24ddeeb507a1c5bbbcbf2d3dad4be8213114b4ce8d",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_8_REAL_DEBUG_HOOK_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.8 applied: 0.72 hook acceptance + 3-frame confirmation + narrowed recovery ROI from real debug evidence")

# Pipeline-ready retrigger: v81 verifier/package/workflow are now present on main.
