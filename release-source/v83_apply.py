#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v83_apply.py SOURCE_ROOT")

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
        raise RuntimeError(f"V0.1.10 expected exactly one {label}, found {count}")
    write(path, text.replace(old, new, 1))


base_audit_path = root / "V0_1_9_HUD_FALLBACK_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1.9 audit missing; v83 must be applied to V0.1.9/v82 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.9":
    raise RuntimeError("unexpected public base version for v83")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.9";',
             'public const string CurrentVersion = "V0.1.10";',
             "UpdateManager version")
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.9</Version>", "<Version>0.1.10</Version>", "project Version")
replace_once(project, "<AssemblyVersion>0.1.9.0</AssemblyVersion>", "<AssemblyVersion>0.1.10.0</AssemblyVersion>", "project AssemblyVersion")
replace_once(project, "<FileVersion>0.1.9.0</FileVersion>", "<FileVersion>0.1.10.0</FileVersion>", "project FileVersion")

bot_path = app / "FishingBot.cs"
bot = read(bot_path)

# Extract the existing audited compass condition instead of guessing its configured
# threshold. V0.1.9 added a color-only hook HUD fallback before this compass branch,
# so a compass-like circular HUD could be treated as a hook and Space was pressed.
compass_re = re.compile(
    r'var\s+compass\s*=\s*_templates\.MatchCompass\(f\.Gray,\s*slot\);\s*\r?\n\s*if\s*\((?P<cond>[^\r\n]+)\)'
)
compass_match = compass_re.search(bot)
if not compass_match:
    raise RuntimeError("V0.1.10 could not locate the existing compass recognition branch")
compass_condition = compass_match.group("cond").strip()
if "compass" not in compass_condition:
    raise RuntimeError(f"V0.1.10 unexpected compass condition: {compass_condition}")
priority_condition = re.sub(r'\bcompass\b', 'compassPriority', compass_condition)
inline_condition = re.sub(r'\bcompass\b', '_templates.MatchCompass(f.Gray, slot)', compass_condition)

old_stage1 = '''            double hookThreshold = Math.Min(_cfg.HookThreshold, 0.72);
            bool hookHud = LooksLikeFishingCastHud(f.Bgr);
            if (hook.Score >= hookThreshold || hookHud)
            {'''
new_stage1 = f'''            double hookThreshold = Math.Min(_cfg.HookThreshold, 0.72);
            // V0.1.10: compass has strict priority over every hook signal. The circular
            // compass HUD can share green/white/red colors with the fishing hook HUD,
            // so never allow the color fallback (or even a cross-matched hook template)
            // to send Space while the compass template is present. The existing else
            // branch below remains responsible for S -> wait -> hook -> Space.
            var compassPriority = _templates.MatchCompass(f.Gray, slot);
            bool compassPresent = {priority_condition};
            bool hookHud = !compassPresent && LooksLikeFishingCastHud(f.Bgr);
            if (!compassPresent && (hook.Score >= hookThreshold || hookHud))
            {{'''
if bot.count(old_stage1) != 1:
    raise RuntimeError(f"V0.1.10 expected one V0.1.9 stage1 HUD block, found {bot.count(old_stage1)}")
bot = bot.replace(old_stage1, new_stage1, 1)

# V0.1.9 also added the same color fallback to two post-cast hook-ready checks.
# Gate those checks with the existing compass template as well, so compass can never
# be interpreted as a hook just because its colors resemble the cast button.
old_post = 'if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72) || LooksLikeFishingCastHud(f.Bgr))'
post_count = bot.count(old_post)
if post_count != 2:
    raise RuntimeError(f"V0.1.10 expected two V0.1.9 post-cast HUD checks, found {post_count}")
new_post = f'if (!({inline_condition}) && (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72) || LooksLikeFishingCastHud(f.Bgr)))'
bot = bot.replace(old_post, new_post)

# Keep diagnostics explicit: if the compass is winning the decision, show it rather
# than reporting only a low Hook score. This makes future Telegram stall reports useful.
old_diag = 'Status($"시전 대기 · Hook {hook.Score:F2} x{hook.Scale:F2}");'
new_diag = 'Status(compassPresent ? $"시전 대기 · 나침반 우선 {compassPriority.Score:F2} · S 전환" : $"시전 대기 · Hook {hook.Score:F2} x{hook.Scale:F2}");'
if bot.count(old_diag) != 1:
    raise RuntimeError("V0.1.10 could not update stage1 status diagnostics")
bot = bot.replace(old_diag, new_diag, 1)
write(bot_path, bot)

# Retained behavior: the actual S key path is intentionally left in the existing
# compass else-branch; we only restore its priority ahead of Space.
for marker in (
    'var compassPriority = _templates.MatchCompass(f.Gray, slot);',
    'bool compassPresent =',
    'bool hookHud = !compassPresent && LooksLikeFishingCastHud(f.Bgr);',
    'if (!compassPresent && (hook.Score >= hookThreshold || hookHud))',
    'Math.Min(_cfg.HookThreshold, 0.72)',
    'if (hookFrames >= 3)',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도',
):
    if marker not in bot:
        raise RuntimeError(f"V0.1.10 required fishing invariant missing: {marker}")

# Verify that the original compass branch still exists after the priority patch.
if not compass_re.search(bot):
    raise RuntimeError("V0.1.10 accidentally removed the original compass -> S branch")

config_path = app / "config.json"
config_text = read(config_path)
if '"HookThreshold": 0.72' not in config_text:
    raise RuntimeError("V0.1.10 must preserve V0.1.9 HookThreshold 0.72")

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
        raise RuntimeError(f"V0.1.10 requires V0.1.8 matcher invariant: {marker}")

capture_path = app / "CaptureService.cs"
capture = read(capture_path)
for marker in (
    'NativeMethods.GetClientRect(window.Handle, out var liveClient)',
    'NativeMethods.ClientToScreen(window.Handle, ref liveOrigin)',
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);',
):
    if marker not in capture:
        raise RuntimeError(f"V0.1.10 requires live capture/focus invariant: {marker}")

changes = root / "CHANGES_V0.1.10_COMPASS_PRIORITY.txt"
changes.write_text(
    "MABI AUTO V0.1.10 - compass priority before fishing hook\n"
    "- Fixes the V0.1.9 regression where the color HUD fallback could classify the circular compass state as a fishing hook and press Space immediately.\n"
    "- Stage 1 now evaluates the existing compass template first. While compass is present, every hook signal is blocked and the original compass branch handles S.\n"
    "- Only after compass is absent can the 0.72 hook template or lower-center HUD fallback accumulate the existing 3-frame confirmation and send Space.\n"
    "- The same compass exclusion guards the two post-cast hook-ready checks so the regression cannot reappear between rounds.\n"
    "- Telegram/status diagnostics now show compass-priority state when it is blocking hook recognition.\n"
    "- V0.1.9 HUD fallback, V0.1.8 three-frame confirmation, V0.1.7 live capture/debug, V0.1.6 foreground recovery and V0.1.5 gauge resync/input retry remain enabled.\n",
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
    root / "START.cmd",
    changes,
]
audit = {
    "base_public_version": "V0.1.9",
    "technical_bridge_base": "v82",
    "technical_bridge_tag": "v83",
    "version": "V0.1.10",
    "purpose": "Restore compass-first S transition before any fishing-hook Space decision",
    "compass_condition_reused": compass_condition,
    "decision_order": ["compass template", "S transition via existing branch", "hook template/HUD fallback", "3-frame confirmation", "Space"],
    "hook_threshold": 0.72,
    "hook_confirm_frames": 3,
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_10_COMPASS_PRIORITY_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.10 applied: compass template has strict priority; compass -> S -> hook -> Space")
