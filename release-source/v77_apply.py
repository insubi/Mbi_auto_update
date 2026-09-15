#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v77_apply.py SOURCE_ROOT")

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
        raise RuntimeError(f"V0.1.4 expected exactly one {label}, found {count}")
    write(path, text.replace(old, new, 1))


base_audit_path = root / "V0_1_3_FISHING_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1.3 audit missing; v77 must be applied to V0.1.3/v76 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.3":
    raise RuntimeError("unexpected public base version for v77")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.3";',
             'public const string CurrentVersion = "V0.1.4";',
             "UpdateManager version")
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.3</Version>", "<Version>0.1.4</Version>", "project Version")
replace_once(project, "<AssemblyVersion>0.1.3.0</AssemblyVersion>", "<AssemblyVersion>0.1.4.0</AssemblyVersion>", "project AssemblyVersion")
replace_once(project, "<FileVersion>0.1.3.0</FileVersion>", "<FileVersion>0.1.4.0</FileVersion>", "project FileVersion")

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

    public static bool Activate()
    {
        IntPtr target = FindGameWindow();
        if (target == IntPtr.Zero)
            return false;

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

input_candidates = []
for path in app.rglob("*.cs"):
    if path == focus_path:
        continue
    text = read(path)
    if re.search(r"\bbool\s+TapSpace\s*\(\s*\)", text):
        input_candidates.append(path)
if len(input_candidates) != 1:
    raise RuntimeError(f"V0.1.4 expected one TapSpace backend, found {len(input_candidates)}: {input_candidates}")

input_path = input_candidates[0]
input_text = read(input_path)
method_pattern = re.compile(
    r"(?m)^(?P<indent>[ \t]*)"
    r"(?P<sig>(?:public|internal|private|protected)\s+(?:static\s+)?(?:bool|void)\s+"
    r"(?P<name>(?:Tap|Press|Send|Key|Hold|Release)\w*)\s*\([^)]*\)\s*\{)[ \t]*$"
)
patched_methods = []


def add_focus(match: re.Match) -> str:
    name = match.group("name")
    indent = match.group("indent")
    patched_methods.append(name)
    return match.group(0) + "\n" + indent + "    global::FishingFocusGuard.Activate();"

input_text, count = method_pattern.subn(add_focus, input_text)
if count == 0 or "Tap" not in patched_methods:
    raise RuntimeError(f"V0.1.4 could not guard low-level Tap; methods found={patched_methods}")
write(input_path, input_text)

bot_text = read(app / "FishingBot.cs")
for marker in (
    "double hookThreshold = Math.Min(_cfg.HookThreshold, 0.82);",
    "bool sent = _input.TapSpace();",
    "Space 전송 실패 -> 재시도",
):
    if marker not in bot_text:
        raise RuntimeError(f"V0.1.4 requires V0.1.3 fishing invariant: {marker}")

changes = root / "CHANGES_V0.1.4_FOCUS_BEFORE_KEYBOARD.txt"
changes.write_text(
    "MABI AUTO V0.1.4 - focus before keyboard input\n"
    "- Every fishing low-level Tap method now activates the real '마비노기 모바일' window immediately before injection.\n"
    "- Foreground recovery uses AttachThreadInput + BringWindowToTop + SetForegroundWindow + SetFocus so clicking another app no longer strands Space input there.\n"
    "- The target is resolved by visible game-window title and largest client area on every send, so stale HWND/focus state is not reused.\n"
    "- Minimized game windows are restored before input.\n"
    "- V0.1.3 current hook template, two-frame 0.82 recognition and failed-Space retry remain unchanged.\n"
    "- V0.1.2 Abyss stabilization, HOME UI, Telegram, administrator elevation and 800x1000 placement remain unchanged.\n",
    encoding="utf-8",
)

tracked = [
    app / "UpdateManager.cs",
    project,
    focus_path,
    input_path,
    changes,
]
audit = {
    "base_public_version": "V0.1.3",
    "technical_bridge_base": "v76",
    "technical_bridge_tag": "v77",
    "version": "V0.1.4",
    "purpose": "Activate the real game window immediately before every fishing keyboard injection",
    "keyboard_input_file": input_path.relative_to(root).as_posix(),
    "guarded_methods": sorted(set(patched_methods)),
    "focus_strategy": [
        "resolve visible titled game window on every send",
        "restore minimized window",
        "AttachThreadInput to foreground and target threads",
        "BringWindowToTop",
        "SetForegroundWindow",
        "SetActiveWindow",
        "SetFocus",
    ],
    "hook_template_sha256": base_audit.get("hook_template_sha256"),
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_4_FOCUS_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"V0.1.4 applied: foreground guard added to {input_path.name} methods {sorted(set(patched_methods))}")
