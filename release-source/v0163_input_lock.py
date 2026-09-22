#!/usr/bin/env python3
from pathlib import Path
import hashlib
import re
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
input_path = app / "dungeon" / "InputController.cs"
project_path = app / "FishingAutomation.csproj"
update_path = app / "UpdateManager.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

# Audit all runtime/source files so this patch cannot silently alter unrelated logic.
tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
           {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
before = {p.relative_to(root).as_posix(): digest(p) for p in tracked}

s = read(input_path)
class_start = s.find("internal sealed class InterceptionInput : IInputController")
class_end = s.find("// Kept only so older code still compiles.")
if class_start < 0 or class_end < 0 or class_end <= class_start:
    raise SystemExit("InterceptionInput class markers missing")
head = s[:class_start]
body = s[class_start:class_end]
tail = s[class_end:]

field_anchor = """    private readonly nint _context;
    private readonly int _mouseDevice;
    private readonly int _keyboardDevice;
"""
field_new = """    private readonly nint _context;
    private readonly int _mouseDevice;
    private readonly int _keyboardDevice;
    // V0163_GLOBAL_INPUT_LOCK: macro-generated mouse/keyboard input shares one gate.
    // This does not block the user's physical input; it only serializes automation sends.
    private readonly object _inputGate = new();
"""
if body.count(field_anchor) != 1:
    raise SystemExit("InterceptionInput field anchor mismatch")
body = body.replace(field_anchor, field_new, 1)

mode_old = '        $"Interception(mouse={_mouseDevice}, keyboard={_keyboardDevice}, verified-cursor)";'
mode_new = '        $"Interception(mouse={_mouseDevice}, keyboard={_keyboardDevice}, verified-cursor, input-locked)";'
if body.count(mode_old) != 1:
    raise SystemExit("ModeName anchor mismatch")
body = body.replace(mode_old, mode_new, 1)

click_anchor = """    public void ClickClientPoint(nint hwnd, Point clientPoint)
    {
"""
click_new = """    public void ClickClientPoint(nint hwnd, Point clientPoint)
    {
        lock (_inputGate)
        {
            ClickClientPointCore(hwnd, clientPoint);
        }
    }

    private void ClickClientPointCore(nint hwnd, Point clientPoint)
    {
"""
if body.count(click_anchor) != 1:
    raise SystemExit("Interception click method anchor mismatch")
body = body.replace(click_anchor, click_new, 1)

key_anchor = """    public void TapScanCode(ushort scanCode)
    {
"""
key_new = """    public void TapScanCode(ushort scanCode)
    {
        lock (_inputGate)
        {
            TapScanCodeCore(scanCode);
        }
    }

    private void TapScanCodeCore(ushort scanCode)
    {
"""
if body.count(key_anchor) != 1:
    raise SystemExit("Interception key method anchor mismatch")
body = body.replace(key_anchor, key_new, 1)

write(input_path, head + body + tail)

project = read(project_path)
for old, new in (
    ("<Version>0.1.62</Version>", "<Version>0.1.63</Version>"),
    ("<AssemblyVersion>0.1.62.0</AssemblyVersion>", "<AssemblyVersion>0.1.63.0</AssemblyVersion>"),
    ("<FileVersion>0.1.62.0</FileVersion>", "<FileVersion>0.1.63.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.62"' not in update:
    raise SystemExit("UpdateManager V0.1.62 marker missing")
update = update.replace('CurrentVersion = "V0.1.62"', 'CurrentVersion = "V0.1.63"', 1)
write(update_path, update)

# Static verification.
patched = read(input_path)
for marker in (
    "V0163_GLOBAL_INPUT_LOCK",
    "private readonly object _inputGate = new();",
    "lock (_inputGate)",
    "ClickClientPointCore(hwnd, clientPoint);",
    "TapScanCodeCore(scanCode);",
    "verified-cursor, input-locked",
):
    if marker not in patched:
        raise SystemExit(f"input lock marker missing: {marker}")

# Both automation input entrypoints must be serialized by the SAME gate.
interception = patched[patched.index("internal sealed class InterceptionInput"):
                       patched.index("// Kept only so older code still compiles.")]
if interception.count("lock (_inputGate)") != 2:
    raise SystemExit("expected exactly two Interception input gate entrypoints")

# No behavior change is allowed outside InputController + version metadata.
allowed = {
    input_path.relative_to(root).as_posix(),
    project_path.relative_to(root).as_posix(),
    update_path.relative_to(root).as_posix(),
}
after_tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                 {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
after = {p.relative_to(root).as_posix(): digest(p) for p in after_tracked}
changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
unexpected = sorted(changed - allowed)
if unexpected:
    raise SystemExit("unexpected runtime/source changes: " + ", ".join(unexpected))

if "<Version>0.1.63</Version>" not in read(project_path):
    raise SystemExit("project version not V0.1.63")
if 'CurrentVersion = "V0.1.63"' not in read(update_path):
    raise SystemExit("updater version not V0.1.63")

print("V0.1.63 applied: shared internal input lock for Dungeon/Abyss Interception mouse+keyboard")
