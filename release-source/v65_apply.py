#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"v65 expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


# Version bump v64 -> v65 while preserving the v64 administrator/window fixes.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v64";',
                 'public const string CurrentVersion = "v65";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "65.0.0"), ("AssemblyVersion", "65.0.0.0"), ("FileVersion", "65.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v65 project version tag missing: {name}")
write(project, s)

# Real-use log showed abyss_popup_close firing on unrelated OCR strings such as
# '나가기', which can destroy the normal Abyss flow while another target is
# being awaited. The visual popup-close template already exists, so this target
# no longer falls back to OCR at all.
targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(targets_path.read_text(encoding="utf-8-sig"))
popup = [t for t in targets if t.get("Id") == "abyss_popup_close"]
if len(popup) != 1:
    raise RuntimeError(f"v65 expected one abyss_popup_close target, found {len(popup)}")
popup = popup[0]
if not popup.get("TemplatePath"):
    raise RuntimeError("v65 abyss_popup_close template path is missing")

popup["Kind"] = "template"
popup.pop("Text", None)
popup.pop("MaxEditDistance", None)
popup.pop("OcrRetryAt2x", None)
# Keep the proven visual threshold/ROI/scales from v64 to avoid introducing a
# new false-negative risk; only the unsafe OCR fallback is removed.
targets_path.write_text(json.dumps(targets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Slow repeat clicks slightly. This does not affect first detection, but keeps a
# single popup from receiving repeated clicks while the UI is transitioning.
scenario_path = app / "abyss" / "config" / "scenario.json"
scenario = json.loads(scenario_path.read_text(encoding="utf-8-sig"))
monitors = [m for m in scenario.get("Monitors", []) if m.get("Target") == "abyss_popup_close"]
if len(monitors) != 1:
    raise RuntimeError(f"v65 expected one abyss_popup_close monitor, found {len(monitors)}")
monitors[0]["CooldownMs"] = max(int(monitors[0].get("CooldownMs", 0)), 3000)
monitors[0]["ScanIntervalMs"] = max(int(monitors[0].get("ScanIntervalMs", 0)), 1000)
scenario_path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# Advance visible UI version labels without changing UI behavior.
ui_files = [app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs"]
for p in ui_files:
    s = read(p)
    s = s.replace('v64.0.0', 'v65.0.0')
    s = s.replace('Dashboard v64', 'Dashboard v65')
    s = s.replace('v64  |  Mabi Auto', 'v65  |  Mabi Auto')
    write(p, s)

changes = root / "CHANGES_v65_ABYSS_POPUP_GUARD.txt"
changes.write_text(
    "MABI AUTO v65\n"
    "- Abyss popup-close monitor no longer uses OCR fallback.\n"
    "- abyss_popup_close is visual-template only, preventing unrelated text such as 나가기 from being clicked as a popup close.\n"
    "- Popup-close monitor cooldown is increased to reduce repeated clicks during UI transitions.\n"
    "- Abyss scene-skip, treasure chest, normal exit, timeout recovery and retry logic are otherwise unchanged.\n"
    "- v64 administrator elevation, exact 800x1000 sizing and dual-monitor handling are retained.\n",
    encoding="utf-8",
)

modified = [update, project, targets_path, scenario_path] + ui_files + [changes]
audit = {
    "base": "v64",
    "version": "v65",
    "purpose": "prevent Abyss popup-close OCR false positives from clicking normal controls",
    "popup_close_detection": "template-only; OCR fallback removed",
    "monitor_cooldown_ms": monitors[0]["CooldownMs"],
    "monitor_scan_interval_ms": monitors[0]["ScanIntervalMs"],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V65_ABYSS_POPUP_AUDIT.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("v65 Abyss popup false-click guard applied")
