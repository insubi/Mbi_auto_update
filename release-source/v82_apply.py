#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v82_apply.py SOURCE_ROOT")

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
        raise RuntimeError(f"V0.1.9 expected exactly one {label}, found {count}")
    write(path, text.replace(old, new, 1))


base_audit_path = root / "V0_1_8_REAL_DEBUG_HOOK_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1.8 audit missing; v82 must be applied to V0.1.8/v81 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.8":
    raise RuntimeError("unexpected public base version for v82")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.8";',
             'public const string CurrentVersion = "V0.1.9";',
             "UpdateManager version")
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.8</Version>", "<Version>0.1.9</Version>", "project Version")
replace_once(project, "<AssemblyVersion>0.1.8.0</AssemblyVersion>", "<AssemblyVersion>0.1.9.0</AssemblyVersion>", "project AssemblyVersion")
replace_once(project, "<FileVersion>0.1.8.0</FileVersion>", "<FileVersion>0.1.9.0</FileVersion>", "project FileVersion")

bot_path = app / "FishingBot.cs"
bot = read(bot_path)

old_stage1 = '''            double hookThreshold = Math.Min(_cfg.HookThreshold, 0.72);\n            if (hook.Score >= hookThreshold)\n            {'''
new_stage1 = '''            double hookThreshold = Math.Min(_cfg.HookThreshold, 0.72);\n            bool hookHud = LooksLikeFishingCastHud(f.Bgr);\n            if (hook.Score >= hookThreshold || hookHud)\n            {'''
if bot.count(old_stage1) != 1:
    raise RuntimeError(f"V0.1.9 could not patch stage1 hook decision; found {bot.count(old_stage1)}")
bot = bot.replace(old_stage1, new_stage1, 1)

old_status = 'Status($"낚싯대 인식 {hook.Score:F2} · Space 입력");'
new_status = 'Status($"낚싯대 인식 {hook.Score:F2} · {(hook.Score >= hookThreshold ? "템플릿" : "HUD보조")} · Space 입력");'
if bot.count(old_status) != 1:
    raise RuntimeError("V0.1.9 could not enrich stage1 hook status")
bot = bot.replace(old_status, new_status, 1)

raw_hook = 'if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72))'
raw_count = bot.count(raw_hook)
if raw_count != 2:
    raise RuntimeError(f"V0.1.9 expected two post-cast hook checks, found {raw_count}")
bot = bot.replace(raw_hook, 'if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72) || LooksLikeFishingCastHud(f.Bgr))')

insert_marker = '    private async Task<GaugeAnchor?> WaitFirstGauge(GameWindow window, CancellationToken ct)\n'
if bot.count(insert_marker) != 1:
    raise RuntimeError("V0.1.9 could not locate WaitFirstGauge insertion point")
helper = '''    private static bool LooksLikeFishingCastHud(OpenCvSharp.Mat bgr)\n    {\n        if (bgr.Empty() || bgr.Width < 100 || bgr.Height < 100) return false;\n\n        // The cast HUD is anchored to the lower screen center. Instead of relying only\n        // on the gray hook crop (whose correlation changes with the translucent\n        // background), verify the stable green ring + white hook + red tip colors.\n        // Sampling every second pixel keeps this cheap enough for the 80 ms loop.\n        int left = Math.Clamp((int)Math.Round(bgr.Width * 0.42), 0, bgr.Width - 1);\n        int right = Math.Clamp((int)Math.Round(bgr.Width * 0.58), left + 1, bgr.Width);\n        int top = Math.Clamp((int)Math.Round(bgr.Height * 0.80), 0, bgr.Height - 1);\n        int bottom = Math.Clamp((int)Math.Round(bgr.Height * 0.94), top + 1, bgr.Height);\n\n        int green = 0;\n        int white = 0;\n        int red = 0;\n        for (int y = top; y < bottom; y += 2)\n        {\n            for (int x = left; x < right; x += 2)\n            {\n                OpenCvSharp.Vec3b p = bgr.At<OpenCvSharp.Vec3b>(y, x);\n                int b = p.Item0, g = p.Item1, r = p.Item2;\n                if (g >= 105 && g - r >= 15 && g - b >= 15) green++;\n                if (r >= 200 && g >= 200 && b >= 200) white++;\n                if (r >= 150 && r - g >= 25 && r - b >= 25) red++;\n            }\n        }\n\n        return green >= 240 && white >= 35 && red >= 5;\n    }\n\n'''
bot = bot.replace(insert_marker, helper + insert_marker, 1)
write(bot_path, bot)

for marker in (
    'Math.Min(_cfg.HookThreshold, 0.72)',
    'if (hookFrames >= 3)',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도',
    'LooksLikeFishingCastHud(f.Bgr)',
):
    if marker not in bot:
        raise RuntimeError(f"V0.1.9 retained/fallback invariant missing: {marker}")

config_path = app / "config.json"
config_text = read(config_path)
if '"HookThreshold": 0.72' not in config_text:
    raise RuntimeError("V0.1.9 must preserve V0.1.8 HookThreshold 0.72")

matcher_path = app / "TemplateMatcher.cs"
matcher = read(matcher_path)
for marker in (
    'if (primary.Score >= 0.72) return primary;',
    'gray.Width * 0.28',
    'gray.Width * 0.72',
    'gray.Height * 0.72',
    'gray.Height * 0.97',
):
    if marker not in matcher:
        raise RuntimeError(f"V0.1.9 requires V0.1.8 matcher invariant: {marker}")

capture_path = app / "CaptureService.cs"
capture = read(capture_path)
for marker in (
    'NativeMethods.GetClientRect(window.Handle, out var liveClient)',
    'NativeMethods.ClientToScreen(window.Handle, ref liveOrigin)',
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);',
):
    if marker not in capture:
        raise RuntimeError(f"V0.1.9 requires live capture/focus invariant: {marker}")

start_path = root / "START.cmd"
start = read(start_path)
if 'copy /y "%ROOT%\\FishingAutomation\\templates\\hook.png" "%ROOT%\\release\\templates\\hook.png"' not in start:
    raise RuntimeError("V0.1.9 requires runtime hook refresh")

changes = root / "CHANGES_V0.1.9_HUD_FALLBACK.txt"
changes.write_text(
    "MABI AUTO V0.1.9 - fixed-position fishing HUD fallback\n"
    "- V0.1.8 could still miss the cast button when gray-template correlation fluctuated across consecutive animated frames.\n"
    "- The existing 0.72 template path remains primary. A second independent detector now checks only the fixed lower-center HUD region for the green circular ring, white hook glyph and red hook tip.\n"
    "- HUD fallback uses the same multi-frame stage confirmation, so it does not turn a single transient color match into a Space press.\n"
    "- The fallback is also used when waiting for the hook button to reappear after a round, preventing post-catch stalls caused by the same template/background sensitivity.\n"
    "- V0.1.8 three-frame confirmation, V0.1.7 live ClientToScreen capture-origin refresh and 8-second debug capture, V0.1.6 foreground recovery, and V0.1.5 gauge resync/input retry are preserved.\n",
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
    "base_public_version": "V0.1.8",
    "technical_bridge_base": "v81",
    "technical_bridge_tag": "v82",
    "version": "V0.1.9",
    "purpose": "Recognize the fixed lower-center fishing cast HUD even when translucent-background template correlation fluctuates",
    "primary_hook_threshold": 0.72,
    "primary_hook_confirm_frames": 3,
    "hud_roi": "42%-58% width, 80%-94% height",
    "hud_sample_step": 2,
    "hud_min_green": 240,
    "hud_min_white": 35,
    "hud_min_red": 5,
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_9_HUD_FALLBACK_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.9 applied: fixed lower-center HUD color fallback + V0.1.8 template path preserved")

# Pipeline-ready retrigger after v82 verifier/package/workflow landed on main.
# This no-op comment intentionally retriggers Publish Release Source once the v82 pipeline is present.
