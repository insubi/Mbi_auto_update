#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, json, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v76_apply.py SOURCE_ROOT")

root = Path(sys.argv[1])
app = root / "FishingAutomation"

def replace_once(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise RuntimeError(f"V0.1.3 marker not found in {path}: {old[:80]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.2";',
             'public const string CurrentVersion = "V0.1.3";')
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.2</Version>", "<Version>0.1.3</Version>")
replace_once(project, "<AssemblyVersion>0.1.2.0</AssemblyVersion>", "<AssemblyVersion>0.1.3.0</AssemblyVersion>")
replace_once(project, "<FileVersion>0.1.2.0</FileVersion>", "<FileVersion>0.1.3.0</FileVersion>")

bot = app / "FishingBot.cs"
old_cast = '''            if (hook.Score >= _cfg.HookThreshold)
            {
                hookFrames++;
                compassFrames = 0;
                if (hookFrames >= 2)
                {
                    _log.Write($"낚싯대 아이콘 {hook.Score:F3} scale={hook.Scale:F2}, 2프레임 -> Space");
                    WindowLocator.ActivateForInput(window);
                    Status($"낚싯대 인식 {hook.Score:F2} · Space 입력");
                    _input.TapSpace();
                    await Task.Delay(120, ct);
                    return true;
                }
            }'''
new_cast = '''            // V0.1.3: the current circular fishing HUD is slightly softer than the
            // legacy crop after game/client scaling. Keep two-frame confirmation and
            // the narrow Hook ROI, but cap stale user configs at the audited threshold.
            double hookThreshold = Math.Min(_cfg.HookThreshold, 0.82);
            if (hook.Score >= hookThreshold)
            {
                hookFrames++;
                compassFrames = 0;
                if (hookFrames >= 2)
                {
                    WindowLocator.ActivateForInput(window);
                    Status($"낚싯대 인식 {hook.Score:F2} · Space 입력");
                    bool sent = _input.TapSpace();
                    if (!sent)
                    {
                        _log.Write($"낚싯대 아이콘 {hook.Score:F3} 인식, Space 전송 실패 -> 재시도");
                        hookFrames = 0;
                        await Task.Delay(250, ct);
                        continue;
                    }
                    _log.Write($"낚싯대 아이콘 {hook.Score:F3} scale={hook.Scale:F2}, 2프레임 -> Space");
                    await Task.Delay(120, ct);
                    return true;
                }
            }'''
replace_once(bot, old_cast, new_cast)

config = app / "config.json"
replace_once(config, '"HookThreshold": 0.85', '"HookThreshold": 0.82')

start = root / "START.cmd"
for name in ("hook.png", "gauge.png", "healthbar.png", "compass.png"):
    plain = f'copy /y "%ROOT%\\FishingAutomation\\templates\\{name}" "%ROOT%\\release\\templates\\{name}" >nul'
    guarded = f'if not exist "%ROOT%\\release\\templates\\{name}" copy /y "%ROOT%\\FishingAutomation\\templates\\{name}" "%ROOT%\\release\\templates\\{name}" >nul'
    replace_once(start, plain, guarded)

hook_data = base64.b64decode("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", validate=True)
if not hook_data.startswith(b"\x89PNG\r\n\x1a\n"):
    raise RuntimeError("V0.1.3 hook payload is not PNG")
hook_path = app / "templates" / "hook.png"
hook_path.write_bytes(hook_data)

changes = root / "CHANGES_V0.1.3_FISHING_TEMPLATE.txt"
changes.write_text("""V0.1.3 fishing start regression fix
- Replaces the obsolete water/rod hook template with the current circular Space fishing HUD crop.
- START.cmd no longer overwrites an already working runtime template on every launch.
- Existing 0.85 user configs are safely capped at 0.82 inside the narrow Hook ROI with two-frame confirmation.
- A failed Interception Space send is no longer logged as successful progress and is retried.
- Package verification checks the exact hook asset, guarded template copy, and fishing source markers.
""", encoding="utf-8")

tracked = [
    "FishingAutomation/UpdateManager.cs",
    "FishingAutomation/FishingAutomation.csproj",
    "FishingAutomation/FishingBot.cs",
    "FishingAutomation/config.json",
    "FishingAutomation/templates/hook.png",
    "START.cmd",
    "CHANGES_V0.1.3_FISHING_TEMPLATE.txt",
]
audit = {
    "base_public_version": "V0.1.2",
    "technical_bridge_base": "v75",
    "technical_bridge_tag": "v76",
    "version": "V0.1.3",
    "purpose": "Restore current fishing-start detection and preserve working runtime templates across launch/update",
    "hook_template_sha256": hashlib.sha256(hook_data).hexdigest(),
    "files": {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in tracked},
}
(root / "V0_1_3_FISHING_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.3 applied: current hook template + no launch overwrite + truthful Space retry")
