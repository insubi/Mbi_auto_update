#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v78_apply.py SOURCE_ROOT")

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
        raise RuntimeError(f"V0.1.5 expected exactly one {label}, found {count}")
    write(path, text.replace(old, new, 1))

base_audit_path = root / "V0_1_4_FOCUS_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1.4 audit missing; v78 must be applied to V0.1.4/v77 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.4":
    raise RuntimeError("unexpected public base version for v78")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.4";',
             'public const string CurrentVersion = "V0.1.5";',
             "UpdateManager version")
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.4</Version>", "<Version>0.1.5</Version>", "project Version")
replace_once(project, "<AssemblyVersion>0.1.4.0</AssemblyVersion>", "<AssemblyVersion>0.1.5.0</AssemblyVersion>", "project AssemblyVersion")
replace_once(project, "<FileVersion>0.1.4.0</FileVersion>", "<FileVersion>0.1.5.0</FileVersion>", "project FileVersion")

bot = app / "FishingBot.cs"
text = read(bot)
old_threshold = 'double hookThreshold = Math.Min(_cfg.HookThreshold, 0.82);'
if text.count(old_threshold) != 1:
    raise RuntimeError(f"V0.1.5 expected one stage1 hook threshold marker, found {text.count(old_threshold)}")
text = text.replace(old_threshold, 'double hookThreshold = Math.Min(_cfg.HookThreshold, 0.78);', 1)

old_raw = 'if (hook.Score >= _cfg.HookThreshold)'
raw_count = text.count(old_raw)
if raw_count != 2:
    raise RuntimeError(f"V0.1.5 expected two raw hook threshold checks, found {raw_count}")
text = text.replace(old_raw, 'if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.78))')

old_locals = '''        DateTime lastCompassTap = DateTime.MinValue;
        DateTime lastDiagnostic = DateTime.MinValue;
        int hookFrames = 0;'''
new_locals = '''        DateTime lastCompassTap = DateTime.MinValue;
        DateTime lastDiagnostic = DateTime.MinValue;
        DateTime lastGaugeResync = DateTime.MinValue;
        int hookFrames = 0;'''
if text.count(old_locals) != 1:
    raise RuntimeError("V0.1.5 could not add stage1 gauge-resync timer")
text = text.replace(old_locals, new_locals, 1)

old_else = '''            else
            {
                hookFrames = 0;

                var compass = _templates.MatchCompass(f.Gray, slot);'''
new_else = '''            else
            {
                hookFrames = 0;

                // V0.1.5: stage resync. If the user pressed Space manually, or an
                // earlier input reached the game while stage 1 still believed it was
                // waiting for the hook icon, the live gauge is authoritative evidence
                // that fishing has already started. Move forward instead of waiting
                // forever for the hook icon to come back.
                if (DateTime.UtcNow - lastGaugeResync >= TimeSpan.FromMilliseconds(250))
                {
                    lastGaugeResync = DateTime.UtcNow;
                    GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);
                    if (liveGauge is not null)
                    {
                        _log.Write($"상태 복구: 시전 대기 중 게이지 감지 score={liveGauge.Score:F3}, scale={liveGauge.Scale:F2} -> 게이지 단계");
                        Status($"진행 중 게이지 감지 {liveGauge.Score:F2} · 상태 복구");
                        return true;
                    }
                }

                var compass = _templates.MatchCompass(f.Gray, slot);'''
if text.count(old_else) != 1:
    raise RuntimeError("V0.1.5 could not insert stage1 gauge resync")
text = text.replace(old_else, new_else, 1)
write(bot, text)

config = app / "config.json"
replace_once(config, '"HookThreshold": 0.82', '"HookThreshold": 0.78', "HookThreshold")

changes = root / "CHANGES_V0.1.5_FISHING_RESYNC.txt"
changes.write_text(
    "MABI AUTO V0.1.5 - fishing start recognition and state resync\n"
    "- Lowers the effective hook threshold from 0.82 to 0.78 inside the same narrow bottom-center ROI with two-frame confirmation.\n"
    "- Applies the same effective threshold to start, second-round exit detection, and next-round return detection.\n"
    "- Stage 1 now checks for a live gauge every 250 ms; if manual Space or a previous input already started fishing, it resynchronizes into the gauge stage instead of waiting forever for the hook icon.\n"
    "- Keeps V0.1.4 game-window focus recovery before keyboard injection.\n"
    "- Keeps V0.1.3 current hook template and truthful Interception retry.\n",
    encoding="utf-8",
)

tracked = [app / "UpdateManager.cs", project, bot, config, app / "FishingFocusGuard.cs", app / "InputSender.cs", changes]
audit = {
    "base_public_version": "V0.1.4",
    "technical_bridge_base": "v77",
    "technical_bridge_tag": "v78",
    "version": "V0.1.5",
    "purpose": "Recognize the current hook HUD reliably and resync stage 1 when fishing is already in progress",
    "effective_hook_threshold": 0.78,
    "stage1_gauge_resync_ms": 250,
    "hook_template_sha256": base_audit.get("hook_template_sha256"),
    "keyboard_input_file": base_audit.get("keyboard_input_file"),
    "guarded_methods": base_audit.get("guarded_methods"),
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_5_FISHING_RESYNC_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.5 applied: hook threshold 0.78 + stage1 live-gauge resync + V0.1.4 focus guard preserved")
