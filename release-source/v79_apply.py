#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v79_apply.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = read(path)
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != 1:
        raise RuntimeError(f"V0.1.6 expected exactly one {label}, found {count}")
    write(path, text.replace(old, new, 1))


base_audit_path = root / "V0_1_5_FISHING_RESYNC_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1.5 audit missing; v79 must be applied to V0.1.5/v78 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.5":
    raise RuntimeError("unexpected public base version for v79")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.5";',
             'public const string CurrentVersion = "V0.1.6";',
             "UpdateManager version")
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.5</Version>", "<Version>0.1.6</Version>", "project Version")
replace_once(project, "<AssemblyVersion>0.1.5.0</AssemblyVersion>", "<AssemblyVersion>0.1.6.0</AssemblyVersion>", "project AssemblyVersion")
replace_once(project, "<FileVersion>0.1.5.0</FileVersion>", "<FileVersion>0.1.6.0</FileVersion>", "project FileVersion")

focus_path = app / "FishingFocusGuard.cs"
focus_code = r'''using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

internal static class FishingFocusGuard
{
    private const int SW_RESTORE = 9;

    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextLengthW(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextW(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    private static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool BringWindowToTop(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern IntPtr SetActiveWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern IntPtr SetFocus(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();

    [DllImport("user32.dll")]
    private static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);

    public static bool IsForeground(IntPtr target)
        => target != IntPtr.Zero && GetForegroundWindow() == target;

    public static bool Activate()
    {
        IntPtr target = FindGameWindow();
        return Activate(target);
    }

    public static bool Activate(IntPtr target)
    {
        if (target == IntPtr.Zero)
            return false;

        if (IsForeground(target))
            return true;

        if (IsIconic(target))
        {
            ShowWindow(target, SW_RESTORE);
            Thread.Sleep(40);
        }

        IntPtr foreground = GetForegroundWindow();
        uint currentThread = GetCurrentThreadId();
        uint targetThread = GetWindowThreadProcessId(target, out _);
        uint foregroundThread = foreground != IntPtr.Zero
            ? GetWindowThreadProcessId(foreground, out _)
            : 0;

        bool attachedForeground = false;
        bool attachedTarget = false;
        try
        {
            if (foregroundThread != 0 && foregroundThread != currentThread)
                attachedForeground = AttachThreadInput(currentThread, foregroundThread, true);

            if (targetThread != 0 && targetThread != currentThread && targetThread != foregroundThread)
                attachedTarget = AttachThreadInput(currentThread, targetThread, true);

            BringWindowToTop(target);
            SetForegroundWindow(target);
            SetActiveWindow(target);
            SetFocus(target);
        }
        finally
        {
            if (attachedTarget)
                AttachThreadInput(currentThread, targetThread, false);
            if (attachedForeground)
                AttachThreadInput(currentThread, foregroundThread, false);
        }

        Thread.Sleep(35);
        if (GetForegroundWindow() != target)
        {
            SetForegroundWindow(target);
            Thread.Sleep(20);
        }
        return GetForegroundWindow() == target;
    }

    private static IntPtr FindGameWindow()
    {
        IntPtr best = IntPtr.Zero;
        long bestArea = -1;

        EnumWindows((hWnd, _) =>
        {
            if (!IsWindowVisible(hWnd))
                return true;

            int length = GetWindowTextLengthW(hWnd);
            if (length <= 0)
                return true;

            var titleBuffer = new StringBuilder(length + 1);
            GetWindowTextW(hWnd, titleBuffer, titleBuffer.Capacity);
            string title = titleBuffer.ToString();
            if (!title.Contains("마비노기 모바일", StringComparison.OrdinalIgnoreCase))
                return true;

            long area = 0;
            if (GetClientRect(hWnd, out var rect))
                area = Math.Max(0, rect.Right - rect.Left) * (long)Math.Max(0, rect.Bottom - rect.Top);

            if (area > bestArea)
            {
                bestArea = area;
                best = hWnd;
            }
            return true;
        }, IntPtr.Zero);

        return best;
    }
}
'''
write(focus_path, focus_code)

native_path = app / "NativeMethods.cs"
native = read(native_path)
old_activate = '''    public static void ActivateForInput(GameWindow window)
    {
        try
        {
            if (NativeMethods.IsIconic(window.Handle))
                NativeMethods.ShowWindow(window.Handle, NativeMethods.SW_RESTORE);
            NativeMethods.BringWindowToTop(window.Handle);
            NativeMethods.SetForegroundWindow(window.Handle);
            Thread.Sleep(45);
        }
        catch { }
    }'''
new_activate = '''    public static void ActivateForInput(GameWindow window)
    {
        try
        {
            global::FishingFocusGuard.Activate(window.Handle);
            Thread.Sleep(45);
        }
        catch { }
    }'''
if native.count(old_activate) != 1:
    raise RuntimeError(f"V0.1.6 expected one weak WindowLocator activation block, found {native.count(old_activate)}")
write(native_path, native.replace(old_activate, new_activate, 1))

capture_path = app / "CaptureService.cs"
capture = read(capture_path)
old_capture = '''    public CapturedFrame Capture(GameWindow window)
    {
        var bmp = new Bitmap(window.ClientWidth, window.ClientHeight, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.CopyFromScreen(window.ClientScreenOrigin.X, window.ClientScreenOrigin.Y, 0, 0,
                new System.Drawing.Size(window.ClientWidth, window.ClientHeight), CopyPixelOperation.SourceCopy);
        }
        return new CapturedFrame(bmp);
    }'''
new_capture = '''    public CapturedFrame Capture(GameWindow window)
    {
        // V0.1.6: this capture path reads the physical desktop. If Mabi_Auto,
        // a browser, or any other window is in front of the game, CopyFromScreen
        // would capture that window instead of the game and every template score
        // would collapse. Restore the exact game HWND before reading screen pixels.
        if (!global::FishingFocusGuard.IsForeground(window.Handle))
        {
            global::FishingFocusGuard.Activate(window.Handle);
            Thread.Sleep(70);
        }

        var bmp = new Bitmap(window.ClientWidth, window.ClientHeight, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.CopyFromScreen(window.ClientScreenOrigin.X, window.ClientScreenOrigin.Y, 0, 0,
                new System.Drawing.Size(window.ClientWidth, window.ClientHeight), CopyPixelOperation.SourceCopy);
        }
        return new CapturedFrame(bmp);
    }'''
if capture.count(old_capture) != 1:
    raise RuntimeError(f"V0.1.6 expected one physical screen capture block, found {capture.count(old_capture)}")
write(capture_path, capture.replace(old_capture, new_capture, 1))

main_path = app / "MainForm.cs"
main = read(main_path)
old_field = '''    private DateTime _lastFishingProgressAt = DateTime.Now;
    private bool _fishingStallAlerted;'''
new_field = '''    private DateTime _lastFishingProgressAt = DateTime.Now;
    private bool _fishingStallAlerted;
    private string _lastFishingStatus = "준비";'''
if main.count(old_field) != 1:
    raise RuntimeError("V0.1.6 could not add last fishing status field")
main = main.replace(old_field, new_field, 1)

old_status = '''        _fishingBot.StatusChanged += s => Ui(() =>
        {
            if (SelectedMode == "낚시" && (_activeMode is null || _activeMode == "낚시"))
                SetStatus(_fishingBot.IsRunning ? s : "준비 완료", _fishingBot.IsRunning ? Blue : Green);
        });'''
new_status = '''        _fishingBot.StatusChanged += s => Ui(() =>
        {
            _lastFishingStatus = s;
            if (SelectedMode == "낚시" && (_activeMode is null || _activeMode == "낚시"))
                SetStatus(_fishingBot.IsRunning ? s : "준비 완료", _fishingBot.IsRunning ? Blue : Green);
        });'''
if main.count(old_status) != 1:
    raise RuntimeError("V0.1.6 could not track fishing status")
main = main.replace(old_status, new_status, 1)

old_alert = '_ = _notifier.SendAlertAsync("낚시 매크로 진행 정지 감지", $"{seconds}초 이상 정상 진행 신호가 없습니다.", true);'
new_alert = '_ = _notifier.SendAlertAsync("낚시 매크로 진행 정지 감지", $"{seconds}초 이상 정상 진행 신호가 없습니다.\\n현재 상태: {_lastFishingStatus}", true);'
if main.count(old_alert) != 1:
    raise RuntimeError("V0.1.6 could not enrich fishing stall alert")
main = main.replace(old_alert, new_alert, 1)
write(main_path, main)

# Ensure the V0.1.5 recognition/resync behavior remains present.
bot_path = app / "FishingBot.cs"
bot = read(bot_path)
for marker in (
    'double hookThreshold = Math.Min(_cfg.HookThreshold, 0.78);',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도',
):
    if marker not in bot:
        raise RuntimeError(f"V0.1.6 requires V0.1.5 fishing invariant: {marker}")

config_path = app / "config.json"
config_text = read(config_path)
if '"HookThreshold": 0.78' not in config_text:
    raise RuntimeError("V0.1.6 requires V0.1.5 HookThreshold 0.78")

changes = root / "CHANGES_V0.1.6_FOREGROUND_CAPTURE.txt"
changes.write_text(
    "MABI AUTO V0.1.6 - foreground-aware physical screen capture\n"
    "- Root cause correction: the 22:10 screenshot matches the current hook asset strongly after normalization, so lowering the threshold again is not the right fix.\n"
    "- CaptureService uses CopyFromScreen, which reads whatever window is physically on top. It now restores the exact game HWND before every capture when the game is not foreground.\n"
    "- WindowLocator keyboard activation is routed through the same AttachThreadInput/SetForegroundWindow/SetFocus recovery path.\n"
    "- 60-second fishing stall Telegram alerts now include the last live fishing status (for example Hook/Gauge score/state).\n"
    "- V0.1.5 0.78 two-frame hook recognition and live-gauge state resync are preserved.\n"
    "- Note: because the current vision backend is physical screen capture, another desktop window cannot remain over the game while fishing automation is active; the game is brought forward when needed.\n",
    encoding="utf-8",
)

tracked = [
    app / "UpdateManager.cs",
    project,
    focus_path,
    native_path,
    capture_path,
    main_path,
    bot_path,
    config_path,
    changes,
]
audit = {
    "base_public_version": "V0.1.5",
    "technical_bridge_base": "v78",
    "technical_bridge_tag": "v79",
    "version": "V0.1.6",
    "purpose": "Ensure physical CopyFromScreen capture sees the game by restoring the exact game HWND whenever foreground is lost",
    "capture_backend": "CopyFromScreen with exact-HWND foreground recovery",
    "foreground_settle_ms": 70,
    "effective_hook_threshold": 0.78,
    "stage1_gauge_resync_ms": 250,
    "hook_template_sha256": base_audit.get("hook_template_sha256"),
    "keyboard_input_file": base_audit.get("keyboard_input_file"),
    "guarded_methods": base_audit.get("guarded_methods"),
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_6_FOREGROUND_CAPTURE_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.6 applied: foreground-aware physical capture + robust exact-HWND activation + richer stall diagnostics")
