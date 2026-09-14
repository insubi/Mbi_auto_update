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
        raise RuntimeError(f"v60 expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


# Version bump v59 -> v60.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v59";',
                 'public const string CurrentVersion = "v60";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "60.0.0"), ("AssemblyVersion", "60.0.0.0"), ("FileVersion", "60.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v60 project version tag missing: {name}")
write(project, s)

# Fishing placement: always target the PRIMARY monitor. If the window crosses
# from a secondary monitor with a different DPI, re-measure after the move
# instead of returning immediately with stale frame/client dimensions.
native = app / "NativeMethods.cs"
s = read(native)
old_fishing = '''    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)
    {
        try
        {
            if (NativeMethods.IsIconic(hwnd))
            {
                NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
                Thread.Sleep(120);
            }

            bool changed = false;
            for (int attempt = 0; attempt < 5; attempt++)
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
                    Rectangle area = Screen.FromHandle(hwnd).WorkingArea;
                    NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, area.Right - outerW, area.Top, outerW, outerH,
                        NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);
                    if (changed)
                        log.Write($"게임 창 맞춤 완료: 클라이언트 {clientW}x{clientH} · 우상단");
                    return;
                }

                int targetOuterW = Math.Max(1, outerW + (cfg.ClientWidth - clientW));
                int targetOuterH = Math.Max(1, outerH + (cfg.ClientHeight - clientH));
                Rectangle work = Screen.FromHandle(hwnd).WorkingArea;

                if (!NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, work.Right - targetOuterW, work.Top,
                    targetOuterW, targetOuterH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE))
                    return;

                changed = true;
                Thread.Sleep(attempt == 0 ? 220 : 120);
            }

            if (NativeMethods.GetClientRect(hwnd, out var finalRect))
            {
                int finalW = finalRect.Right - finalRect.Left;
                int finalH = finalRect.Bottom - finalRect.Top;
                log.Write($"게임 창 맞춤 결과: {finalW}x{finalH} (목표 {cfg.ClientWidth}x{cfg.ClientHeight})");
            }
        }
        catch (Exception ex)
        {
            log.Write("게임 창 자동 맞춤 실패: " + ex.Message);
        }
    }'''
new_fishing = '''    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)
    {
        try
        {
            if (NativeMethods.IsIconic(hwnd))
            {
                NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
                Thread.Sleep(120);
            }

            bool changed = false;
            for (int attempt = 0; attempt < 7; attempt++)
            {
                if (!NativeMethods.GetWindowRect(hwnd, out var wr) ||
                    !NativeMethods.GetClientRect(hwnd, out var cr))
                    return;

                int clientW = cr.Right - cr.Left;
                int clientH = cr.Bottom - cr.Top;
                int outerW = wr.Right - wr.Left;
                int outerH = wr.Bottom - wr.Top;
                var currentScreen = Screen.FromHandle(hwnd);
                var primaryScreen = Screen.PrimaryScreen ?? currentScreen;
                Rectangle work = primaryScreen.WorkingArea;
                bool onPrimary = currentScreen.Primary;

                if (Math.Abs(clientW - cfg.ClientWidth) <= 1 &&
                    Math.Abs(clientH - cfg.ClientHeight) <= 1)
                {
                    if (!NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, work.Right - outerW, work.Top, outerW, outerH,
                        NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE))
                        return;

                    changed = true;
                    if (onPrimary)
                    {
                        log.Write($"게임 창 맞춤 완료: 주 모니터 · 클라이언트 {clientW}x{clientH} · 우상단");
                        return;
                    }

                    // Crossing monitors can change non-client metrics at a new DPI.
                    // Re-measure on the primary monitor before declaring success.
                    Thread.Sleep(220);
                    continue;
                }

                int targetOuterW = Math.Max(1, outerW + (cfg.ClientWidth - clientW));
                int targetOuterH = Math.Max(1, outerH + (cfg.ClientHeight - clientH));

                if (!NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, work.Right - targetOuterW, work.Top,
                    targetOuterW, targetOuterH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE))
                    return;

                changed = true;
                Thread.Sleep(attempt == 0 || !onPrimary ? 220 : 120);
            }

            if (NativeMethods.GetClientRect(hwnd, out var finalRect))
            {
                int finalW = finalRect.Right - finalRect.Left;
                int finalH = finalRect.Bottom - finalRect.Top;
                log.Write($"게임 창 맞춤 결과: 주 모니터 {finalW}x{finalH} (목표 {cfg.ClientWidth}x{cfg.ClientHeight})");
            }
        }
        catch (Exception ex)
        {
            log.Write("게임 창 자동 맞춤 실패: " + ex.Message);
        }
    }'''
s = replace_once(s, old_fishing, new_fishing, 'Fishing TryPlaceWindow v59 implementation')
write(native, s)

# Dungeon/Abyss placement gets the same primary-monitor and cross-DPI recheck.
window_tools = app / "dungeon" / "WindowTools.cs"
s = read(window_tools)
old_dungeon = '''    public static void EnsureClientSizeAndTopRight(
        nint hwnd,
        int clientWidth,
        int clientHeight)
    {
        if (!IsRequiredGameWindow(hwnd))
            return;

        for (int attempt = 0; attempt < 5; attempt++)
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
                var area = Screen.FromHandle(hwnd).WorkingArea;
                NativeMethods.SetWindowPos(hwnd, 0, area.Right - outerW, area.Top, outerW, outerH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);
                return;
            }

            int newOuterW = Math.Max(1, outerW + (clientWidth - clientW));
            int newOuterH = Math.Max(1, outerH + (clientHeight - clientH));
            var screen = Screen.FromHandle(hwnd).WorkingArea;

            NativeMethods.SetWindowPos(hwnd, 0, screen.Right - newOuterW, screen.Top,
                newOuterW, newOuterH,
                NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);

            Thread.Sleep(attempt == 0 ? 220 : 120);
        }
    }'''
new_dungeon = '''    public static void EnsureClientSizeAndTopRight(
        nint hwnd,
        int clientWidth,
        int clientHeight)
    {
        if (!IsRequiredGameWindow(hwnd))
            return;

        for (int attempt = 0; attempt < 7; attempt++)
        {
            if (!NativeMethods.GetWindowRect(hwnd, out var wr) ||
                !NativeMethods.GetClientRect(hwnd, out var cr))
                return;

            int outerW = wr.Right - wr.Left;
            int outerH = wr.Bottom - wr.Top;
            int clientW = cr.Right - cr.Left;
            int clientH = cr.Bottom - cr.Top;
            var currentScreen = Screen.FromHandle(hwnd);
            var primaryScreen = Screen.PrimaryScreen ?? currentScreen;
            var work = primaryScreen.WorkingArea;
            bool onPrimary = currentScreen.Primary;

            if (Math.Abs(clientW - clientWidth) <= 1 &&
                Math.Abs(clientH - clientHeight) <= 1)
            {
                NativeMethods.SetWindowPos(hwnd, 0, work.Right - outerW, work.Top, outerW, outerH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);

                if (onPrimary)
                    return;

                Thread.Sleep(220);
                continue;
            }

            int newOuterW = Math.Max(1, outerW + (clientWidth - clientW));
            int newOuterH = Math.Max(1, outerH + (clientHeight - clientH));

            NativeMethods.SetWindowPos(hwnd, 0, work.Right - newOuterW, work.Top,
                newOuterW, newOuterH,
                NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE);

            Thread.Sleep(attempt == 0 || !onPrimary ? 220 : 120);
        }
    }'''
s = replace_once(s, old_dungeon, new_dungeon, 'Dungeon EnsureClientSizeAndTopRight v59 implementation')
write(window_tools, s)

changes = root / "CHANGES_v60_DUAL_MONITOR.txt"
changes.write_text(
    "MABI AUTO v60\n"
    "- Dual-monitor placement fix: macro start now targets the PRIMARY monitor top-right.\n"
    "- When moving from a secondary monitor with a different DPI, client size is re-measured after the move.\n"
    "- Fishing, Dungeon and Abyss keep the required 800x1000 client geometry.\n"
    "- v59 repeated client-size correction, v58 packaging and v57 updater/watchdog fixes remain intact.\n",
    encoding="utf-8",
)

modified = [update, project, native, window_tools, changes]
audit = {
    "base": "v59",
    "version": "v60",
    "purpose": "dual-monitor primary-screen placement with cross-DPI remeasurement",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V60_DUAL_MONITOR_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print("v60 dual-monitor primary-screen correction applied")
