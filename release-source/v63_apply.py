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
        raise RuntimeError(f"v63 expected exactly one {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


# Version bump v62 -> v63.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v62";',
                 'public const string CurrentVersion = "v63";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "63.0.0"), ("AssemblyVersion", "63.0.0.0"), ("FileVersion", "63.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v63 project version tag missing: {name}")

# Embed an application manifest that always asks Windows for administrator rights.
# Real-use diagnostics from v62 showed Win32 error 5 (Access Denied) for both
# SetWindowPos and MoveWindow; running MABI AUTO elevated fixed the resize.
if '<ApplicationManifest>' in s:
    s = re.sub(r'<ApplicationManifest>[^<]*</ApplicationManifest>',
               '<ApplicationManifest>app.manifest</ApplicationManifest>', s, count=1)
else:
    marker = '<UseWindowsForms>true</UseWindowsForms>'
    if marker in s:
        s = s.replace(marker, marker + '\n    <ApplicationManifest>app.manifest</ApplicationManifest>', 1)
    else:
        pos = s.find('</PropertyGroup>')
        if pos < 0:
            raise RuntimeError('v63 could not find a PropertyGroup for ApplicationManifest')
        s = s[:pos] + '  <ApplicationManifest>app.manifest</ApplicationManifest>\n' + s[pos:]
write(project, s)

manifest = app / "app.manifest"
manifest.write_text('''<?xml version="1.0" encoding="utf-8"?>
<assembly manifestVersion="1.0" xmlns="urn:schemas-microsoft-com:asm.v1">
  <assemblyIdentity version="1.0.0.0" name="MabiAuto.FishingAutomation" />
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false" />
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}" />
    </application>
  </compatibility>
</assembly>
''', encoding='utf-8')

# v62 proved that extra MoveWindow/WINDOWPLACEMENT fallbacks cannot bypass an
# integrity-level mismatch. Keep the useful v59/v60 behavior (exact client size,
# primary monitor, repeated DPI re-measurement) but simplify the resize path to
# one SetWindowPos loop and one actionable error message.
native = app / "NativeMethods.cs"
s = read(native)
start = s.index('    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)')
class_end = s.rfind('\n}')
if class_end <= start:
    raise RuntimeError('v63 could not locate WindowLocator class end')
new_fishing = r'''    private static void TryPlaceWindow(IntPtr hwnd, AutomationConfig cfg, AppLog log)
    {
        try
        {
            if (NativeMethods.IsIconic(hwnd) || NativeMethods.IsZoomed(hwnd))
            {
                NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
                Thread.Sleep(220);
            }

            var primary = Screen.PrimaryScreen ?? Screen.FromHandle(hwnd);
            Rectangle work = primary.WorkingArea;

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
                    int x = work.Right - outerW;
                    if (!NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, x, work.Top, outerW, outerH,
                        NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED))
                    {
                        int error = Marshal.GetLastWin32Error();
                        log.Write($"게임 창 위치 변경 실패: Win32 {error} (관리자 권한 확인)");
                        return;
                    }

                    log.Write($"게임 창 맞춤 완료: {clientW}x{clientH} · 주 모니터 우상단");
                    return;
                }

                int targetOuterW = Math.Max(1, outerW + (cfg.ClientWidth - clientW));
                int targetOuterH = Math.Max(1, outerH + (cfg.ClientHeight - clientH));
                int targetX = work.Right - targetOuterW;

                if (!NativeMethods.SetWindowPos(hwnd, IntPtr.Zero, targetX, work.Top,
                    targetOuterW, targetOuterH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED))
                {
                    int error = Marshal.GetLastWin32Error();
                    log.Write($"게임 창 크기 변경 실패: Win32 {error} (관리자 권한 확인)");
                    return;
                }

                Thread.Sleep(attempt == 0 ? 240 : 140);
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
    }
'''
s = s[:start] + new_fishing + s[class_end:]
write(native, s)

# Dungeon/Abyss: same simplified, elevated SetWindowPos-only geometry path.
window_tools = app / "dungeon" / "WindowTools.cs"
s = read(window_tools)
start = s.index('    public static void EnsureClientSizeAndTopRight(')
class_end = s.rfind('\n}')
if class_end <= start:
    raise RuntimeError('v63 could not locate WindowTools class end')
new_dungeon = r'''    public static void EnsureClientSizeAndTopRight(
        nint hwnd,
        int clientWidth,
        int clientHeight)
    {
        if (!IsRequiredGameWindow(hwnd))
            return;

        if (NativeMethods.IsIconic(hwnd) || NativeMethods.IsZoomed(hwnd))
        {
            NativeMethods.ShowWindow(hwnd, NativeMethods.SW_RESTORE);
            Thread.Sleep(220);
        }

        var primary = Screen.PrimaryScreen ?? Screen.FromHandle(hwnd);
        var work = primary.WorkingArea;

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
                NativeMethods.SetWindowPos(hwnd, 0, work.Right - outerW, work.Top, outerW, outerH,
                    NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED);
                return;
            }

            int targetOuterW = Math.Max(1, outerW + (clientWidth - clientW));
            int targetOuterH = Math.Max(1, outerH + (clientHeight - clientH));

            if (!NativeMethods.SetWindowPos(hwnd, 0, work.Right - targetOuterW, work.Top,
                targetOuterW, targetOuterH,
                NativeMethods.SWP_NOZORDER | NativeMethods.SWP_NOACTIVATE | NativeMethods.SWP_FRAMECHANGED))
                return;

            Thread.Sleep(attempt == 0 ? 240 : 140);
        }
    }
'''
s = s[:start] + new_dungeon + s[class_end:]
write(window_tools, s)

# Advance visible UI version labels.
ui_files = [app / "MainForm.Dashboard.cs", app / "MainForm.ReferenceUI.cs"]
for p in ui_files:
    s = read(p)
    s = s.replace('v62.0.0', 'v63.0.0')
    s = s.replace('Dashboard v62', 'Dashboard v63')
    s = s.replace('v62  |  Mabi Auto', 'v63  |  Mabi Auto')
    write(p, s)

changes = root / "CHANGES_v63_ADMIN_WINDOW_CLEANUP.txt"
changes.write_text(
    "MABI AUTO v63\n"
    "- Root cause confirmed from v62 real-use diagnostics: Win32 error 5 (Access Denied).\n"
    "- FishingAutomation.exe now requests administrator privileges automatically via app.manifest.\n"
    "- Keeps exact 800x1000 client sizing, primary-monitor top-right placement and dual-monitor re-measurement.\n"
    "- Keeps v62 visible game-window selection.\n"
    "- Removes repeated MoveWindow/WINDOWPLACEMENT resize fallback behavior and noisy retry diagnostics.\n"
    "- v57 updater/watchdog, v56 retry recognition and v58 safe packaging remain intact.\n",
    encoding="utf-8",
)

modified = [update, project, manifest, native, window_tools] + ui_files + [changes]
audit = {
    "base": "v62",
    "version": "v63",
    "purpose": "automatic administrator elevation and simplified stable 800x1000 window placement",
    "confirmed_root_cause": "Win32 error 5 Access Denied; manual administrator launch successfully resized the game window",
    "kept": [
        "visible game-window selection",
        "800x1000 client geometry",
        "primary monitor top-right placement",
        "dual-monitor/DPI remeasurement",
        "updater/watchdog fixes",
        "OCR/retry detection",
        "safe packaging"
    ],
    "removed_from_active_resize_path": [
        "MoveWindow fallback",
        "WINDOWPLACEMENT forced restore-bounds fallback",
        "repeated access-denied retry spam"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V63_ADMIN_WINDOW_CLEANUP_AUDIT.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
print("v63 administrator elevation and window cleanup applied")
