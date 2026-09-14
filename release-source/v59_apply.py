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
        raise RuntimeError(f"v59 expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v58";',
                 'public const string CurrentVersion = "v59";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "59.0.0"), ("AssemblyVersion", "59.0.0.0"), ("FileVersion", "59.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v59 project version tag missing: {name}")
write(project, s)

native = app / "NativeMethods.cs"
s = read(native)
if '[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);' not in s:
    anchor = '[DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);'
    s = replace_once(s, anchor,
        anchor + '\n    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);',
        'Fishing GetClientRect import')

s = replace_once(s,
'''        if (cfg.AutoPlaceWindow)\n            TryPlaceWindow(hwnd, cfg, log);''',
'''        // v59: macro start always restores the canonical capture geometry.\n        // Existing user config may have AutoPlaceWindow=false from an older install.\n        TryPlaceWindow(hwnd, cfg, log);''',
'Fishing AutoPlaceWindow gate')

old_fishing = '''    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)\n    {\n        if (!NativeMethods.GetClientRect(hwnd, out var c)) return;\n        int cw = c.Right - c.Left;\n        int ch = c.Bottom - c.Top;\n\n        int style = NativeMethods.GetWindowLong(hwnd, NativeMethods.GWL_STYLE);\n        int exStyle = NativeMethods.GetWindowLong(hwnd, NativeMethods.GWL_EXSTYLE);\n        var outer = new NativeMethods.RECT { Left = 0, Top = 0, Right = cfg.ClientWidth, Bottom = cfg.ClientHeight };\n        if (!NativeMethods.AdjustWindowRectEx(ref outer, unchecked((uint)style), false, unchecked((uint)exStyle))) return;\n\n        int ow = outer.Right - outer.Left;\n        int oh = outer.Bottom - outer.Top;\n        Rectangle area = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1920, 1080);\n        int x = area.Right - ow;\n        int y = area.Top;\n        NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, x, y, ow, oh, NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);\n\n        if (cw != cfg.ClientWidth || ch != cfg.ClientHeight)\n        {\n            Thread.Sleep(250);\n            log.Write($"게임 창을 우상단 {cfg.ClientWidth}x{cfg.ClientHeight} 클라이언트 크기로 맞춤 시도");\n        }\n    }'''
new_fishing = '''    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)\n    {\n        try\n        {\n            if (NativeMethods.IsIconic(hwnd))\n            {\n                NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);\n                Thread.Sleep(120);\n            }\n\n            bool changed = false;\n            for (int attempt = 0; attempt < 5; attempt++)\n            {\n                if (!NativeMethods.GetWindowRect(hwnd, out var wr) ||\n                    !NativeMethods.GetClientRect(hwnd, out var cr))\n                    return;\n\n                int clientW = cr.Right - cr.Left;\n                int clientH = cr.Bottom - cr.Top;\n                int outerW = wr.Right - wr.Left;\n                int outerH = wr.Bottom - wr.Top;\n\n                if (Math.Abs(clientW - cfg.ClientWidth) <= 1 &&\n                    Math.Abs(clientH - cfg.ClientHeight) <= 1)\n                {\n                    Rectangle area = Screen.FromHandle(hwnd).WorkingArea;\n                    NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, area.Right - outerW, area.Top, outerW, outerH,\n                        NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);\n                    if (changed)\n                        log.Write($"게임 창 맞춤 완료: 클라이언트 {clientW}x{clientH} · 우상단");\n                    return;\n                }\n\n                int targetOuterW = Math.Max(1, outerW + (cfg.ClientWidth - clientW));\n                int targetOuterH = Math.Max(1, outerH + (cfg.ClientHeight - clientH));\n                Rectangle work = Screen.FromHandle(hwnd).WorkingArea;\n\n                if (!NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, work.Right - targetOuterW, work.Top,\n                    targetOuterW, targetOuterH,\n                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE))\n                    return;\n\n                changed = true;\n                Thread.Sleep(attempt == 0 ? 220 : 120);\n            }\n\n            if (NativeMethods.GetClientRect(hwnd, out var finalRect))\n            {\n                int finalW = finalRect.Right - finalRect.Left;\n                int finalH = finalRect.Bottom - finalRect.Top;\n                log.Write($"게임 창 맞춤 결과: {finalW}x{finalH} (목표 {cfg.ClientWidth}x{cfg.ClientHeight})");\n            }\n        }\n        catch (Exception ex)\n        {\n            log.Write("게임 창 자동 맞춤 실패: " + ex.Message);\n        }\n    }'''
s = replace_once(s, old_fishing, new_fishing, 'Fishing TryPlaceWindow implementation')
write(native, s)

window_tools = app / "dungeon" / "WindowTools.cs"
s = read(window_tools)
old_dungeon = '''    public static void EnsureClientSizeAndTopRight(\n        nint hwnd,\n        int clientWidth,\n        int clientHeight)\n    {\n        if (!IsRequiredGameWindow(hwnd))\n            return;\n\n        if (!NativeMethods.GetWindowRect(hwnd, out var wr) ||\n            !NativeMethods.GetClientRect(hwnd, out var cr))\n            return;\n\n        int outerW = wr.Right - wr.Left;\n        int outerH = wr.Bottom - wr.Top;\n        int clientW = cr.Right - cr.Left;\n        int clientH = cr.Bottom - cr.Top;\n\n        int frameW = outerW - clientW;\n        int frameH = outerH - clientH;\n\n        int newOuterW = clientWidth + frameW;\n        int newOuterH = clientHeight + frameH;\n\n        var screen = Screen.FromHandle(hwnd).WorkingArea;\n\n        int x = screen.Right - newOuterW;\n        int y = screen.Top;\n\n        NativeMethods.SetWindowPos(\n            hwnd,\n            0,\n            x,\n            y,\n            newOuterW,\n            newOuterH,\n            NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);\n    }'''
new_dungeon = '''    public static void EnsureClientSizeAndTopRight(\n        nint hwnd,\n        int clientWidth,\n        int clientHeight)\n    {\n        if (!IsRequiredGameWindow(hwnd))\n            return;\n\n        for (int attempt = 0; attempt < 5; attempt++)\n        {\n            if (!NativeMethods.GetWindowRect(hwnd, out var wr) ||\n                !NativeMethods.GetClientRect(hwnd, out var cr))\n                return;\n\n            int outerW = wr.Right - wr.Left;\n            int outerH = wr.Bottom - wr.Top;\n            int clientW = cr.Right - cr.Left;\n            int clientH = cr.Bottom - cr.Top;\n\n            if (Math.Abs(clientW - clientWidth) <= 1 &&\n                Math.Abs(clientH - clientHeight) <= 1)\n            {\n                var area = Screen.FromHandle(hwnd).WorkingArea;\n                NativeMethods.SetWindowPos(hwnd, 0, area.Right - outerW, area.Top, outerW, outerH,\n                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);\n                return;\n            }\n\n            int newOuterW = Math.Max(1, outerW + (clientWidth - clientW));\n            int newOuterH = Math.Max(1, outerH + (clientHeight - clientH));\n            var screen = Screen.FromHandle(hwnd).WorkingArea;\n\n            NativeMethods.SetWindowPos(hwnd, 0, screen.Right - newOuterW, screen.Top,\n                newOuterW, newOuterH,\n                NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);\n\n            Thread.Sleep(attempt == 0 ? 220 : 120);\n        }\n    }'''
s = replace_once(s, old_dungeon, new_dungeon, 'Dungeon EnsureClientSizeAndTopRight implementation')
write(window_tools, s)

main_form = app / "MainForm.cs"
s = read(main_form)
old_gate = '''            if (settings.ForceClientSizeAndTopRight)\n            {\n                WindowTools.EnsureClientSizeAndTopRight(window.Handle, settings.ClientWidth, settings.ClientHeight);\n                await Task.Delay(500);\n            }'''
new_gate = '''            // v59: Dungeon/Abyss always use the canonical client geometry.\n            WindowTools.EnsureClientSizeAndTopRight(window.Handle, settings.ClientWidth, settings.ClientHeight);\n            await Task.Delay(500);'''
s = replace_once(s, old_gate, new_gate, 'Dungeon/Abyss ForceClientSizeAndTopRight gate')
write(main_form, s)

config = app / "config.json"
cfg = json.loads(config.read_text(encoding="utf-8-sig"))
cfg["ClientWidth"] = 800
cfg["ClientHeight"] = 1000
cfg["AutoPlaceWindow"] = True
config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

for mode in ("dungeon", "abyss"):
    p = app / mode / "config" / "appsettings.json"
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    data["ClientWidth"] = 800
    data["ClientHeight"] = 1000
    data["ForceClientSizeAndTopRight"] = True
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

changes = root / "CHANGES_v59_WINDOW_800x1000.txt"
changes.write_text(
    "MABI AUTO v59\n"
    "- Fishing, Dungeon and Abyss force the game client area to 800x1000 when the macro starts.\n"
    "- The window is anchored to the working area's top-right corner.\n"
    "- Sizing now uses repeated measured-client correction instead of a one-shot frame estimate.\n"
    "- Preserved older config toggles can no longer disable required macro geometry.\n"
    "- v58 packaging, updater/watchdog recovery, retry image+OCR and gameplay logic are otherwise unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, native, window_tools, main_form, config,
            app / "dungeon" / "config" / "appsettings.json",
            app / "abyss" / "config" / "appsettings.json", changes]
audit = {
    "base": "v58",
    "version": "v59",
    "purpose": "force exact 800x1000 client geometry and top-right placement for all macro modes",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V59_WINDOW_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print("v59 800x1000 window correction patch applied")
