#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v84_apply.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

base_audit_path = root / "V0_1_10_COMPASS_PRIORITY_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("v83 V0.1.10 compass-priority audit missing")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.10" or base_audit.get("technical_bridge_tag") != "v83":
    raise RuntimeError("v84 must correct the v83 V0.1.10 bridge source")

bot_path = app / "FishingBot.cs"
bot = read(bot_path)

# v83 correctly restored compass-first behavior in stage 1, but it also tried to
# add a compass guard to two post-cast checks by referencing the stage-1 variable
# 'slot'. One of those methods has no 'slot' local, causing CS0103. Post-cast is
# made conservative instead: template-only Hook check. This cannot confuse the
# color-similar compass HUD with a hook and does not depend on a missing ROI local.
post_guard = re.compile(
    r'if\s*\(!\([^\r\n]*_templates\.MatchCompass\(f\.Gray,\s*slot\)[^\r\n]*\)\s*&&\s*'
    r'\(hook\.Score\s*>=\s*Math\.Min\(_cfg\.HookThreshold,\s*0\.72\)\s*\|\|\s*'
    r'LooksLikeFishingCastHud\(f\.Bgr\)\)\)'
)
matches = list(post_guard.finditer(bot))
if len(matches) != 2:
    raise RuntimeError(f"V0.1.10 finalizer expected two v83 post-cast compass/HUD guards, found {len(matches)}")
bot = post_guard.sub('if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72))', bot)

# The important user-requested order must remain unchanged in the start state:
# compass -> S via original branch -> wait until compass disappears -> Hook -> Space.
for marker in (
    'var compassPriority = _templates.MatchCompass(f.Gray, slot);',
    'bool compassPresent =',
    'bool hookHud = !compassPresent && LooksLikeFishingCastHud(f.Bgr);',
    'if (!compassPresent && (hook.Score >= hookThreshold || hookHud))',
    '시전 대기 · 나침반 우선',
    'var compass = _templates.MatchCompass(f.Gray, slot);',
    'Math.Min(_cfg.HookThreshold, 0.72)',
    'if (hookFrames >= 3)',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도',
):
    if marker not in bot:
        raise RuntimeError(f"V0.1.10 finalizer lost required fishing invariant: {marker}")

if post_guard.search(bot):
    raise RuntimeError("v83 slot-based post-cast guard remains after finalization")
plain_post = bot.count('if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72))')
if plain_post < 2:
    raise RuntimeError(f"expected two conservative post-cast hook checks, found {plain_post}")

write(bot_path, bot)

update = read(app / "UpdateManager.cs")
if 'public const string CurrentVersion = "V0.1.10";' not in update:
    raise RuntimeError("V0.1.10 updater version was lost")
project = read(app / "FishingAutomation.csproj")
for marker in ('<Version>0.1.10</Version>', '<AssemblyVersion>0.1.10.0</AssemblyVersion>', '<FileVersion>0.1.10.0</FileVersion>'):
    if marker not in project:
        raise RuntimeError(f"V0.1.10 project version missing: {marker}")

changes = root / "CHANGES_V0.1.10_COMPASS_PRIORITY_FINAL.txt"
changes.write_text(
    "MABI AUTO V0.1.10 - compass priority final\n"
    "- Start-state order is compass template first; compass blocks both hook template and HUD fallback.\n"
    "- The existing compass branch presses S; only after compass disappears can Hook accumulate 3 frames and send Space.\n"
    "- Corrects the v83 bridge compile-only regression where post-cast guards referenced a stage-local 'slot' outside its method.\n"
    "- Post-cast Hook-ready checks now use the 0.72 Hook template only, preventing the color HUD fallback from confusing compass with Hook between rounds.\n"
    "- Public user version remains V0.1.10; v84 is only the corrected technical bridge.\n",
    encoding="utf-8",
)

tracked = [
    app / "UpdateManager.cs",
    app / "FishingAutomation.csproj",
    bot_path,
    app / "config.json",
    app / "TemplateMatcher.cs",
    app / "CaptureService.cs",
    app / "FishingFocusGuard.cs",
    app / "NativeMethods.cs",
    app / "MainForm.cs",
    root / "START.cmd",
    changes,
]
audit = {
    "base_public_version": "V0.1.10",
    "base_technical_bridge_tag": "v83",
    "technical_bridge_tag": "v84",
    "version": "V0.1.10",
    "purpose": "Finalize compass-first S->Hook->Space order and remove v83 post-cast slot compile regression",
    "decision_order": ["compass template", "S via existing compass branch", "compass absent", "Hook", "3 frames", "Space"],
    "post_cast_detection": "0.72 hook template only",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_10_COMPASS_PRIORITY_FINAL_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.10 final applied on v84: compass -> S -> Hook -> Space; post-cast slot regression removed")
