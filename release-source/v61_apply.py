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
        raise RuntimeError(f"v61 expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


# Version bump v60 -> v61.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v60";',
                 'public const string CurrentVersion = "v61";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "61.0.0"), ("AssemblyVersion", "61.0.0.0"), ("FileVersion", "61.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v61 project version tag missing: {name}")
write(project, s)

# The screenshot from real use showed the client locked at 1358x1000 while the
# target was 800x1000. That is the primary working-area size: the game was still
# maximized. SetWindowPos changes restore bounds but does not shrink a maximized
# top-level window. Explicitly restore maximized windows before measured sizing.
native = app / "NativeMethods.cs"
s = read(native)
iconic_import = '[DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);'
if 'public static extern bool IsZoomed(IntPtr hWnd);' not in s:
    s = replace_once(s, iconic_import,
        iconic_import + '\n    [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr hWnd);',
        'Fishing IsIconic import')

old_restore = '''            if (NativeMethods.IsIconic(hwnd))
            {
                NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
                Thread.Sleep(120);
            }'''
new_restore = '''            if (NativeMethods.IsIconic(hwnd) || NativeMethods.IsZoomed(hwnd))
            {
                bool wasMaximized = NativeMethods.IsZoomed(hwnd);
                NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
                Thread.Sleep(wasMaximized ? 320 : 150);
                if (wasMaximized)
                    log.Write("게임 창 최대화 상태 해제 후 800x1000 보정 시작");
            }'''
s = replace_once(s, old_restore, new_restore, 'Fishing minimized-only restore block')
write(native, s)

# Dungeon/Abyss use their own NativeMethods class.
dungeon_native = app / "dungeon" / "NativeMethods.cs"
s = read(dungeon_native)
iconic_block = '''    [DllImport("user32.dll")]
    public static extern bool IsIconic(nint hWnd);'''
if 'public static extern bool IsZoomed(nint hWnd);' not in s:
    s = replace_once(s, iconic_block,
        iconic_block + '''

    [DllImport("user32.dll")]
    public static extern bool IsZoomed(nint hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(nint hWnd, int nCmdShow);''',
        'Dungeon IsIconic import')
if 'public const int SW_RESTORE = 9;' not in s:
    anchor = '    public const uint SWP_NOACTIVATE = 0x0010;'
    s = replace_once(s, anchor, anchor + '\n    public const int SW_RESTORE = 9;', 'Dungeon SWP constant anchor')
write(dungeon_native, s)

window_tools = app / "dungeon" / "WindowTools.cs"
s = read(window_tools)
old_start = '''        if (!IsRequiredGameWindow(hwnd))
            return;

        for (int attempt = 0; attempt < 7; attempt++)'''
new_start = '''        if (!IsRequiredGameWindow(hwnd))
            return;

        if (NativeMethods.IsZoomed(hwnd))
        {
            NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
            Thread.Sleep(320);
        }

        for (int attempt = 0; attempt < 7; attempt++)'''
s = replace_once(s, old_start, new_start, 'Dungeon/Abyss pre-resize restore')
write(window_tools, s)

# The UI label was never advanced after v55, which made new builds look old.
ui_files = [app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs"]
for p in ui_files:
    s = read(p)
    s = s.replace('v55.0.0', 'v61.0.0')
    s = s.replace('Dashboard v55', 'Dashboard v61')
    s = s.replace('v55  |  Mabi Auto', 'v61  |  Mabi Auto')
    write(p, s)

changes = root / "CHANGES_v61_MAXIMIZED_WINDOW.txt"
changes.write_text(
    "MABI AUTO v61\n"
    "- Fixes the observed 1358x1000 -> 800x1000 failure when the game is maximized.\n"
    "- Fishing restores minimized/maximized state before measured client resizing.\n"
    "- Dungeon/Abyss restore maximized state before the same 800x1000 correction loop.\n"
    "- Primary-monitor dual-screen behavior from v60 remains enabled.\n"
    "- UI version label is updated from the stale v55 label to v61.\n",
    encoding="utf-8",
)

modified = [update, project, native, dungeon_native, window_tools] + ui_files + [changes]
audit = {
    "base": "v60",
    "version": "v61",
    "purpose": "restore maximized game window before 800x1000 resize",
    "observed_failure": "client remained 1358x1000 while target was 800x1000",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V61_WINDOW_STATE_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print("v61 maximized-window resize correction applied")
