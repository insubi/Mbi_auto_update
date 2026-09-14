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
        raise RuntimeError(f"v62 expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


# Version bump v61 -> v62.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v61";',
                 'public const string CurrentVersion = "v62";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "62.0.0"), ("AssemblyVersion", "62.0.0.0"), ("FileVersion", "62.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v62 project version tag missing: {name}")
write(project, s)

# Fishing: prefer the visible game window by title, then fall back to process name.
# Also normalize restore bounds with WINDOWPLACEMENT and use MoveWindow as a fallback.
native = app / "NativeMethods.cs"
s = read(native)

# Add Win32 helpers/flags/struct if absent.
if 'public static extern bool MoveWindow(IntPtr hWnd' not in s:
    s = replace_once(s,
        '[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr insertAfter, int X, int Y, int cx, int cy, uint flags);',
        '[DllImport("user32.dll", SetLastError = true)] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr insertAfter, int X, int Y, int cx, int cy, uint flags);\n'
        '    [DllImport("user32.dll", SetLastError = true)] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);\n'
        '    [DllImport("user32.dll", SetLastError = true)] public static extern bool GetWindowPlacement(IntPtr hWnd, ref WINDOWPLACEMENT lpwndpl);\n'
        '    [DllImport("user32.dll", SetLastError = true)] public static extern bool SetWindowPlacement(IntPtr hWnd, ref WINDOWPLACEMENT lpwndpl);',
        'Fishing SetWindowPos import')

if 'public const uint SWP_FRAMECHANGED' not in s:
    s = replace_once(s,
        '    public const uint SWP_NOACTIVATE = 0x0010;',
        '    public const uint SWP_NOACTIVATE = 0x0010;\n    public const uint SWP_FRAMECHANGED = 0x0020;\n    public const int SW_SHOWNORMAL = 1;',
        'Fishing window flags')

if 'public struct WINDOWPLACEMENT' not in s:
    s = replace_once(s,
        '    [StructLayout(LayoutKind.Sequential)]\n    public struct POINT { public int X, Y; }',
        '    [StructLayout(LayoutKind.Sequential)]\n    public struct POINT { public int X, Y; }\n\n'
        '    [StructLayout(LayoutKind.Sequential)]\n'
        '    public struct WINDOWPLACEMENT\n'
        '    {\n'
        '        public int length;\n'
        '        public int flags;\n'
        '        public int showCmd;\n'
        '        public POINT ptMinPosition;\n'
        '        public POINT ptMaxPosition;\n'
        '        public RECT rcNormalPosition;\n'
        '    }',
        'Fishing POINT struct')

old_lookup = '''        IntPtr hwnd = IntPtr.Zero;

        if (!string.IsNullOrWhiteSpace(cfg.GameProcessName))
        {
            foreach (var p in Process.GetProcessesByName(cfg.GameProcessName))
            {
                try
                {
                    if (p.MainWindowHandle != IntPtr.Zero)
                    {
                        hwnd = p.MainWindowHandle;
                        break;
                    }
                }
                catch { }
            }
        }

        if (hwnd == IntPtr.Zero)
        {
            NativeMethods.EnumWindows((h, _) =>
            {
                if (!NativeMethods.IsWindowVisible(h)) return true;
                int len = NativeMethods.GetWindowTextLength(h);
                if (len <= 0) return true;
                var sb = new StringBuilder(len + 1);
                NativeMethods.GetWindowText(h, sb, sb.Capacity);
                string title = sb.ToString();
                if (!string.IsNullOrWhiteSpace(cfg.GameWindowTitleContains) &&
                    title.Contains(cfg.GameWindowTitleContains, StringComparison.OrdinalIgnoreCase))
                {
                    hwnd = h;
                    return false;
                }
                return true;
            }, IntPtr.Zero);
        }
'''
new_lookup = '''        IntPtr hwnd = IntPtr.Zero;
        long bestArea = -1;

        // Prefer the actual visible game window. Process.MainWindowHandle can point to
        // a stale/secondary top-level window in some multi-monitor/game-launcher states.
        NativeMethods.EnumWindows((h, _) =>
        {
            if (!NativeMethods.IsWindowVisible(h) || NativeMethods.IsIconic(h)) return true;
            int len = NativeMethods.GetWindowTextLength(h);
            if (len <= 0) return true;
            var sb = new StringBuilder(len + 1);
            NativeMethods.GetWindowText(h, sb, sb.Capacity);
            string title = sb.ToString();
            if (!title.Contains("마비노기 모바일", StringComparison.OrdinalIgnoreCase)) return true;
            if (!NativeMethods.GetClientRect(h, out var rr)) return true;
            long area = Math.Max(0, rr.Right - rr.Left) * (long)Math.Max(0, rr.Bottom - rr.Top);
            if (area > bestArea)
            {
                bestArea = area;
                hwnd = h;
            }
            return true;
        }, IntPtr.Zero);

        if (hwnd == IntPtr.Zero && !string.IsNullOrWhiteSpace(cfg.GameProcessName))
        {
            foreach (var p in Process.GetProcessesByName(cfg.GameProcessName))
            {
                try
                {
                    if (p.MainWindowHandle != IntPtr.Zero && NativeMethods.IsWindowVisible(p.MainWindowHandle))
                    {
                        hwnd = p.MainWindowHandle;
                        break;
                    }
                }
                catch { }
            }
        }

        if (hwnd == IntPtr.Zero && !string.IsNullOrWhiteSpace(cfg.GameWindowTitleContains))
        {
            NativeMethods.EnumWindows((h, _) =>
            {
                if (!NativeMethods.IsWindowVisible(h)) return true;
                int len = NativeMethods.GetWindowTextLength(h);
                if (len <= 0) return true;
                var sb = new StringBuilder(len + 1);
                NativeMethods.GetWindowText(h, sb, sb.Capacity);
                if (sb.ToString().Contains(cfg.GameWindowTitleContains, StringComparison.OrdinalIgnoreCase))
                {
                    hwnd = h;
                    return false;
                }
                return true;
            }, IntPtr.Zero);
        }
'''
s = replace_once(s, old_lookup, new_lookup, 'Fishing window lookup')

start = s.index('    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)')
class_end = s.rfind('\n}')
if class_end <= start:
    raise RuntimeError('v62 could not locate WindowLocator class end')
new_func = r'''    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)
    {
        try
        {
            var primary = Screen.PrimaryScreen ?? Screen.FromHandle(hwnd);
            Rectangle work = primary.WorkingArea;

            // Always establish normal restore bounds first. Some game states visually
            // fill the working area without IsZoomed reporting true; ShowWindow alone
            // is therefore not sufficient.
            int style = NativeMethods.GetWindowLong(hwnd, NativeMethods.GWL_STYLE);
            int exStyle = NativeMethods.GetWindowLong(hwnd, NativeMethods.GWL_EXSTYLE);
            var desired = new NativeMethods.RECT { Left = 0, Top = 0, Right = cfg.ClientWidth, Bottom = cfg.ClientHeight };
            int desiredOuterW = cfg.ClientWidth;
            int desiredOuterH = cfg.ClientHeight;
            if (NativeMethods.AdjustWindowRectEx(ref desired, unchecked((uint)style), false, unchecked((uint)exStyle)))
            {
                desiredOuterW = desired.Right - desired.Left;
                desiredOuterH = desired.Bottom - desired.Top;
            }

            int baseX = work.Right - desiredOuterW;
            int baseY = work.Top;
            var wp = new NativeMethods.WINDOWPLACEMENT { length = Marshal.SizeOf<NativeMethods.WINDOWPLACEMENT>() };
            if (NativeMethods.GetWindowPlacement(hwnd, ref wp))
            {
                wp.showCmd = NativeMethods.SW_SHOWNORMAL;
                wp.rcNormalPosition = new NativeMethods.RECT
                {
                    Left = baseX,
                    Top = baseY,
                    Right = baseX + desiredOuterW,
                    Bottom = baseY + desiredOuterH
                };
                NativeMethods.SetWindowPlacement(hwnd, ref wp);
            }

            NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
            Thread.Sleep(260);

            for (int attempt = 0; attempt < 8; attempt++)
            {
                if (!NativeMethods.GetWindowRect(hwnd, out var wr) ||
                    !NativeMethods.GetClientRect(hwnd, out var cr))
                    return;

                int clientW = cr.Right - cr.Left;
                int clientH = cr.Bottom - cr.Top;
                int outerW = wr.Right - wr.Left;
                int outerH = wr.Bottom - wr.Top;

                if (Math.Abs(clientW - cfg.ClientWidth) <= 1 &&
                    Math.Abs(clientH - cfg.ClientHeight) <= 1)
                {
                    int x = work.Right - outerW;
                    int y = work.Top;
                    NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, x, y, outerW, outerH,
                        NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED);
                    log.Write($"게임 창 맞춤 완료: {clientW}x{clientH} · 주 모니터 우상단");
                    return;
                }

                int targetOuterW = Math.Max(1, outerW + (cfg.ClientWidth - clientW));
                int targetOuterH = Math.Max(1, outerH + (cfg.ClientHeight - clientH));
                int targetX = work.Right - targetOuterW;
                int targetY = work.Top;

                bool setOk = NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, targetX, targetY,
                    targetOuterW, targetOuterH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED);
                int setErr = setOk ? 0 : Marshal.GetLastWin32Error();

                Thread.Sleep(120);
                if (NativeMethods.GetClientRect(hwnd, out var after))
                {
                    int afterW = after.Right - after.Left;
                    int afterH = after.Bottom - after.Top;
                    if (Math.Abs(afterW - clientW) <= 1 && Math.Abs(afterH - clientH) <= 1)
                    {
                        bool moveOk = NativeMethods.MoveWindow(hwnd, targetX, targetY, targetOuterW, targetOuterH, true);
                        int moveErr = moveOk ? 0 : Marshal.GetLastWin32Error();
                        if (!setOk || !moveOk)
                            log.Write($"게임 창 크기 변경 호출 실패: SetWindowPos={setOk}({setErr}), MoveWindow={moveOk}({moveErr})");
                    }
                }

                Thread.Sleep(attempt < 2 ? 260 : 160);
            }

            if (NativeMethods.GetClientRect(hwnd, out var finalRect))
            {
                int finalW = finalRect.Right - finalRect.Left;
                int finalH = finalRect.Bottom - finalRect.Top;
                var finalWp = new NativeMethods.WINDOWPLACEMENT { length = Marshal.SizeOf<NativeMethods.WINDOWPLACEMENT>() };
                NativeMethods.GetWindowPlacement(hwnd, ref finalWp);
                log.Write($"게임 창 강제 보정 실패: 현재 {finalW}x{finalH}, 목표 {cfg.ClientWidth}x{cfg.ClientHeight}, showCmd={finalWp.showCmd}, style=0x{unchecked((uint)style):X8}");
            }
        }
        catch (Exception ex)
        {
            log.Write("게임 창 자동 맞춤 실패: " + ex.Message);
        }
    }
'''
s = s[:start] + new_func + s[class_end:]
write(native, s)

# Dungeon/Abyss get the same normal-placement + MoveWindow fallback.
dn = app / "dungeon" / "NativeMethods.cs"
s = read(dn)
if 'public static extern bool MoveWindow(nint hWnd' not in s:
    anchor = '''    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(
        nint hWnd,
        nint hWndInsertAfter,
        int X,
        int Y,
        int cx,
        int cy,
        uint uFlags);'''
    addition = anchor + '''

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool MoveWindow(nint hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetWindowPlacement(nint hWnd, ref WINDOWPLACEMENT lpwndpl);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPlacement(nint hWnd, ref WINDOWPLACEMENT lpwndpl);'''
    s = replace_once(s, anchor, addition, 'Dungeon SetWindowPos import')
if 'public const uint SWP_FRAMECHANGED' not in s:
    s = replace_once(s, '    public const uint SWP_NOACTIVATE = 0x0010;',
        '    public const uint SWP_NOACTIVATE = 0x0010;\n    public const uint SWP_FRAMECHANGED = 0x0020;\n    public const int SW_SHOWNORMAL = 1;',
        'Dungeon window flags')
if 'public struct WINDOWPLACEMENT' not in s:
    marker = '''    public struct POINT
    {
        public int X;
        public int Y;
    }'''
    repl = marker + '''

    [StructLayout(LayoutKind.Sequential)]
    public struct WINDOWPLACEMENT
    {
        public int length;
        public int flags;
        public int showCmd;
        public POINT ptMinPosition;
        public POINT ptMaxPosition;
        public RECT rcNormalPosition;
    }'''
    s = replace_once(s, marker, repl, 'Dungeon POINT struct')
write(dn, s)

wt = app / "dungeon" / "WindowTools.cs"
s = read(wt)
start = s.index('    public static void EnsureClientSizeAndTopRight(')
class_end = s.rfind('\n}')
if class_end <= start:
    raise RuntimeError('v62 could not locate WindowTools class end')
new_dungeon = r'''    public static void EnsureClientSizeAndTopRight(
        nint hwnd,
        int clientWidth,
        int clientHeight)
    {
        if (!IsRequiredGameWindow(hwnd))
            return;

        var primary = Screen.PrimaryScreen ?? Screen.FromHandle(hwnd);
        var work = primary.WorkingArea;

        if (NativeMethods.GetWindowRect(hwnd, out var initialWr) &&
            NativeMethods.GetClientRect(hwnd, out var initialCr))
        {
            int frameW = (initialWr.Right - initialWr.Left) - (initialCr.Right - initialCr.Left);
            int frameH = (initialWr.Bottom - initialWr.Top) - (initialCr.Bottom - initialCr.Top);
            int normalOuterW = Math.Max(1, clientWidth + frameW);
            int normalOuterH = Math.Max(1, clientHeight + frameH);
            int x = work.Right - normalOuterW;
            int y = work.Top;
            var wp = new NativeMethods.WINDOWPLACEMENT { length = Marshal.SizeOf<NativeMethods.WINDOWPLACEMENT>() };
            if (NativeMethods.GetWindowPlacement(hwnd, ref wp))
            {
                wp.showCmd = NativeMethods.SW_SHOWNORMAL;
                wp.rcNormalPosition = new NativeMethods.RECT
                {
                    Left = x, Top = y, Right = x + normalOuterW, Bottom = y + normalOuterH
                };
                NativeMethods.SetWindowPlacement(hwnd, ref wp);
            }
        }

        NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
        Thread.Sleep(260);

        for (int attempt = 0; attempt < 8; attempt++)
        {
            if (!NativeMethods.GetWindowRect(hwnd, out var wr) ||
                !NativeMethods.GetClientRect(hwnd, out var cr))
                return;

            int outerW = wr.Right - wr.Left;
            int outerH = wr.Bottom - wr.Top;
            int clientW = cr.Right - cr.Left;
            int clientH = cr.Bottom - cr.Top;

            if (Math.Abs(clientW - clientWidth) <= 1 &&
                Math.Abs(clientH - clientHeight) <= 1)
            {
                NativeMethods.SetWindowPos(hwnd, 0, work.Right - outerW, work.Top, outerW, outerH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED);
                return;
            }

            int newOuterW = Math.Max(1, outerW + (clientWidth - clientW));
            int newOuterH = Math.Max(1, outerH + (clientHeight - clientH));
            int x = work.Right - newOuterW;
            int y = work.Top;

            NativeMethods.SetWindowPos(hwnd, 0, x, y, newOuterW, newOuterH,
                NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED);
            Thread.Sleep(120);

            if (NativeMethods.GetClientRect(hwnd, out var after) &&
                Math.Abs((after.Right - after.Left) - clientW) <= 1 &&
                Math.Abs((after.Bottom - after.Top) - clientH) <= 1)
            {
                NativeMethods.MoveWindow(hwnd, x, y, newOuterW, newOuterH, true);
            }

            Thread.Sleep(attempt < 2 ? 260 : 160);
        }
    }
'''
s = s[:start] + new_dungeon + s[class_end:]
write(wt, s)

# UI version label.
for p in (app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs"):
    s = read(p)
    s = s.replace('v61.0.0', 'v62.0.0')
    s = s.replace('Dashboard v61', 'Dashboard v62')
    s = s.replace('v61  |  Mabi Auto', 'v62  |  Mabi Auto')
    write(p, s)

changes = root / "CHANGES_v62_WINDOW_FORCE.txt"
changes.write_text(
    "MABI AUTO v62\n"
    "- Fishing now prefers the visible '마비노기 모바일' top-level window instead of blindly taking the first process MainWindowHandle.\n"
    "- Forces normal restore bounds with SetWindowPlacement before resizing.\n"
    "- Adds MoveWindow fallback when SetWindowPos is accepted but the client size does not change.\n"
    "- Uses SWP_FRAMECHANGED and logs showCmd/style when the game still refuses 800x1000.\n"
    "- Dungeon/Abyss use the same stronger placement path.\n"
    "- v61 maximize handling, v60 primary-monitor behavior, updater/watchdog and OCR logic remain intact.\n",
    encoding="utf-8",
)

modified = [update, project, native, dn, wt, app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs", changes]
audit = {
    "base": "v61",
    "version": "v62",
    "purpose": "robust visible-window selection and forced normal restore bounds before 800x1000 resize",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V62_WINDOW_FORCE_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print("v62 robust window placement patch applied")
