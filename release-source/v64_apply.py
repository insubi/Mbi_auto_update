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
        raise RuntimeError(f"v64 expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


# Finalize the cleanup source built on v63.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v63";',
                 'public const string CurrentVersion = "v64";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "64.0.0"), ("AssemblyVersion", "64.0.0.0"), ("FileVersion", "64.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v64 project version tag missing: {name}")
write(project, s)

# Dungeon NativeMethods never exposed SWP_FRAMECHANGED. It is not needed for
# client sizing, so keep the simple stable SetWindowPos flags used before v62.
window_tools = app / "dungeon" / "WindowTools.cs"
s = read(window_tools)
old_flags = 'NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED'
count = s.count(old_flags)
if count != 2:
    raise RuntimeError(f"v64 expected two dungeon SWP_FRAMECHANGED uses, found {count}")
s = s.replace(old_flags, 'NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE')
write(window_tools, s)

# Advance visible UI version labels.
ui_files = [app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs"]
for p in ui_files:
    s = read(p)
    s = s.replace('v63.0.0', 'v64.0.0')
    s = s.replace('Dashboard v63', 'Dashboard v64')
    s = s.replace('v63  |  Mabi Auto', 'v64  |  Mabi Auto')
    write(p, s)

changes = root / "CHANGES_v64_FINAL_CLEANUP.txt"
changes.write_text(
    "MABI AUTO v64\n"
    "- Final cleanup build after confirming Win32 error 5 was caused by privilege mismatch.\n"
    "- Automatic administrator elevation from v63 is retained.\n"
    "- Exact 800x1000 client sizing, primary-monitor top-right placement and dual-monitor handling are retained.\n"
    "- Visible game-window selection from v62 is retained.\n"
    "- Dungeon/Abyss resize flags are simplified to the stable SetWindowPos flags.\n"
    "- v57 updater/watchdog, v56 retry recognition and v58 safe packaging remain intact.\n",
    encoding="utf-8",
)

modified = [update, project, window_tools] + ui_files + [changes]
audit = {
    "base": "v63",
    "version": "v64",
    "purpose": "final administrator-elevation cleanup build",
    "confirmed_root_cause": "Win32 error 5 Access Denied; manual administrator launch successfully resized the game window",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V64_FINAL_CLEANUP_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print("v64 final cleanup applied")
