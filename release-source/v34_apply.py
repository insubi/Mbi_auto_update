from pathlib import Path
import sys

root = Path(sys.argv[1])
app = root / "FishingAutomation"


def load(path: Path, bom=False):
    enc = "utf-8-sig" if bom else "utf-8"
    return path.read_text(encoding=enc), enc


def replace_required(path: Path, old: str, new: str, *, bom=False):
    text, enc = load(path, bom)
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding=enc)


# Macro window title must not contain the game's title string.
replace_required(
    app / "MainForm.cs",
    'Text = "MABI AUTO · 마비노기 모바일 매크로 · v33";',
    'Text = "MABI AUTO · v34";',
    bom=True,
)
replace_required(
    app / "MainForm.Dashboard.cs",
    'Text = "마비노기 모바일 매크로  ·  Dashboard v33",',
    'Text = "자동화 대시보드  ·  Dashboard v34",',
    bom=True,
)
replace_required(
    app / "MainForm.Dashboard.cs",
    'Text = "v33  |  Mabi Auto"',
    'Text = "v34  |  Mabi Auto"',
    bom=True,
)
replace_required(
    app / "UpdateManager.cs",
    'public const string CurrentVersion = "v33";',
    'public const string CurrentVersion = "v34";',
    bom=True,
)

proj = app / "FishingAutomation.csproj"
for old, new in [
    ("<Version>33.0.0</Version>", "<Version>34.0.0</Version>"),
    ("<AssemblyVersion>33.0.0.0</AssemblyVersion>", "<AssemblyVersion>34.0.0.0</AssemblyVersion>"),
    ("<FileVersion>33.0.0.0</FileVersion>", "<FileVersion>34.0.0.0</FileVersion>"),
]:
    replace_required(proj, old, new)

# Wool-gathering target: explicit 1..9999 editor; LifeSettings persists/clamps WoolTarget.
replace_required(
    app / "MainForm.Life.cs",
    'Text = "양털 목표 수량",',
    'Text = "양털 채집 목표 (1~9999)",',
)
replace_required(
    app / "MainForm.Life.cs",
    '_lifeWoolTarget.Maximum = 9999;',
    '_lifeWoolTarget.Maximum = 9999;\n        _lifeWoolTarget.DecimalPlaces = 0;\n        _lifeWoolTarget.ThousandsSeparator = true;',
)

# Defense-in-depth: never treat a window owned by this macro process as the game window.
native = app / "Dungeon" / "NativeMethods.cs"
text = native.read_text(encoding="utf-8")
if "GetWindowThreadProcessId" not in text:
    needle = '    [DllImport("user32.dll")]\n    public static extern int GetWindowTextLength(nint hWnd);\n'
    if needle not in text:
        raise RuntimeError("NativeMethods insertion point not found")
    text = text.replace(
        needle,
        needle + '\n    [DllImport("user32.dll")]\n    public static extern uint GetWindowThreadProcessId(nint hWnd, out uint processId);\n',
        1,
    )
    native.write_text(text, encoding="utf-8")

window_tools = app / "Dungeon" / "WindowTools.cs"
text = window_tools.read_text(encoding="utf-8")
if "processId == (uint)Environment.ProcessId" not in text:
    old = '''            if (!NativeMethods.IsWindowVisible(h)) return true;
            if (NativeMethods.IsIconic(h)) return true;

            var title = GetWindowTitle(h);
'''
    new = '''            if (!NativeMethods.IsWindowVisible(h)) return true;
            if (NativeMethods.IsIconic(h)) return true;

            NativeMethods.GetWindowThreadProcessId(h, out uint processId);
            if (processId == (uint)Environment.ProcessId) return true;

            var title = GetWindowTitle(h);
'''
    if old not in text:
        raise RuntimeError("WindowTools enumerate insertion point not found")
    text = text.replace(old, new, 1)

    old = '''        if (!NativeMethods.IsWindowVisible(hwnd) || NativeMethods.IsIconic(hwnd))
            return false;

        var title = GetWindowTitle(hwnd);
'''
    new = '''        if (!NativeMethods.IsWindowVisible(hwnd) || NativeMethods.IsIconic(hwnd))
            return false;

        NativeMethods.GetWindowThreadProcessId(hwnd, out uint processId);
        if (processId == (uint)Environment.ProcessId)
            return false;

        var title = GetWindowTitle(hwnd);
'''
    if old not in text:
        raise RuntimeError("WindowTools validation insertion point not found")
    text = text.replace(old, new, 1)
    window_tools.write_text(text, encoding="utf-8")

(root / "CHANGES_v34_WINDOW_WOOL.txt").write_text(
    "MABI AUTO v34\n\n"
    "- 매크로 창 제목에서 '마비노기 모바일' 문구 제거\n"
    "- 매크로 자체 프로세스 창은 게임 창 탐색에서 강제 제외\n"
    "- 생활 > 옷감 가공의 양털 채집 목표를 1~9999 범위에서 직접 지정\n"
    "- 양털 목표 수량은 재실행 후에도 유지\n"
    "- 기존 낚시/던전/어비스/생활 기능 유지\n",
    encoding="utf-8",
)

print("v34 patch applied")
