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

# Version bump.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v61";', 'public const string CurrentVersion = "v62";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "62.0.0"), ("AssemblyVersion", "62.0.0.0"), ("FileVersion", "62.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v62 project version tag missing: {name}")
write(project, s)

native = app / "NativeMethods.cs"
s = read(native)

# Stronger Win32 placement helpers for Fishing.
if 'public static extern bool MoveWindow(IntPtr hWnd' not in s:
    s = replace_once(
        s,
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

# Fishing used Process.MainWindowHandle first. Prefer the real visible titled game window.
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
'''
s = replace_once(s, old_lookup, new_lookup, 'Fishing window lookup')

# Replace the complete final TryPlaceWindow method in WindowLocator.
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
            Thread.Sleep(280);

            for (int attempt = 0; attempt < 8; attempt++)
            {
                if (!NativeMethods.GetWindowRect(hwnd, out var wr) || !NativeMethods.GetClientRect(hwnd, out var cr))
                    return;

                int clientW = cr.Right - cr.Left;
                int clientH = cr.Bottom - cr.Top;
                int outerW = wr.Right - wr.Left;
                int outerH = wr.Bottom - wr.Top;

                if (Math.Abs(clientW - cfg.ClientWidth) <= 1 && Math.Abs(clientH - cfg.ClientHeight) <= 1)
                {
                    NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, work.Right - outerW, work.Top, outerW, outerH,
                        NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED);
                    log.Write($"게임 창 맞춤 완료: {clientW}x{clientH} · 주 모니터 우상단");
                    return;
                }

                int targetOuterW = Math.Max(1, outerW + (cfg.ClientWidth - clientW));
                int targetOuterH = Math.Max(1, outerH + (cfg.ClientHeight - clientH));
                int targetX = work.Right - targetOuterW;
                int targetY = work.Top;

                bool setOk = NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, targetX, targetY, targetOuterW, targetOuterH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED);
                int setErr = setOk ? 0 : Marshal.GetLastWin32Error();
                Thread.Sleep(140);

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

                Thread.Sleep(attempt < 2 ? 280 : 180);
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

for p in (app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs"):
    s = read(p)
    s = s.replace('v61.0.0', 'v62.0.0')
    s = s.replace('Dashboard v61', 'Dashboard v62')
    s = s.replace('v61  |  Mabi Auto', 'v62  |  Mabi Auto')
    write(p, s)

changes = root / "CHANGES_v62_WINDOW_FORCE.txt"
changes.write_text(
    "MABI AUTO v62\n"
    "- Fishing prefers the visible '마비노기 모바일' top-level window.\n"
    "- Forces normal restore bounds with SetWindowPlacement before resizing.\n"
    "- Adds MoveWindow fallback when SetWindowPos does not change the client size.\n"
    "- Adds showCmd/style diagnostics if 800x1000 is still refused.\n"
    "- Dungeon/Abyss behavior remains at the stable v61 implementation.\n",
    encoding="utf-8",
)

modified = [update, project, native, app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs", changes]
audit = {
    "base": "v61",
    "version": "v62",
    "purpose": "robust fishing visible-window selection and forced normal restore bounds before 800x1000 resize",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V62_WINDOW_FORCE_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print("v62 corrected fishing window placement patch applied")
