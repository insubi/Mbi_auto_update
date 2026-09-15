#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v80_apply.py SOURCE_ROOT")

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
        raise RuntimeError(f"V0.1.7 expected exactly one {label}, found {count}")
    write(path, text.replace(old, new, 1))


base_audit_path = root / "V0_1_6_FOREGROUND_CAPTURE_AUDIT.json"
if not base_audit_path.is_file():
    raise RuntimeError("V0.1.6 audit missing; v80 must be applied to V0.1.6/v79 source")
base_audit = json.loads(base_audit_path.read_text(encoding="utf-8-sig"))
if base_audit.get("version") != "V0.1.6":
    raise RuntimeError("unexpected public base version for v80")

replace_once(app / "UpdateManager.cs",
             'public const string CurrentVersion = "V0.1.6";',
             'public const string CurrentVersion = "V0.1.7";',
             "UpdateManager version")
project = app / "FishingAutomation.csproj"
replace_once(project, "<Version>0.1.6</Version>", "<Version>0.1.7</Version>", "project Version")
replace_once(project, "<AssemblyVersion>0.1.6.0</AssemblyVersion>", "<AssemblyVersion>0.1.7.0</AssemblyVersion>", "project AssemblyVersion")
replace_once(project, "<FileVersion>0.1.6.0</FileVersion>", "<FileVersion>0.1.7.0</FileVersion>", "project FileVersion")

# Refresh the client origin on every physical-screen capture. The Telegram screenshot
# path already does this; the fishing capture previously kept the origin recorded at F9.
capture_path = app / "CaptureService.cs"
capture = read(capture_path)
old_capture = '''        var bmp = new Bitmap(window.ClientWidth, window.ClientHeight, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.CopyFromScreen(window.ClientScreenOrigin.X, window.ClientScreenOrigin.Y, 0, 0,
                new System.Drawing.Size(window.ClientWidth, window.ClientHeight), CopyPixelOperation.SourceCopy);
        }
        return new CapturedFrame(bmp);'''
new_capture = '''        int captureX = window.ClientScreenOrigin.X;
        int captureY = window.ClientScreenOrigin.Y;
        var liveOrigin = new NativeMethods.POINT { X = 0, Y = 0 };
        if (NativeMethods.GetClientRect(window.Handle, out var liveClient) &&
            liveClient.Right > liveClient.Left && liveClient.Bottom > liveClient.Top &&
            NativeMethods.ClientToScreen(window.Handle, ref liveOrigin))
        {
            captureX = liveOrigin.X;
            captureY = liveOrigin.Y;
        }

        var bmp = new Bitmap(window.ClientWidth, window.ClientHeight, PixelFormat.Format32bppArgb);
        using (Graphics g = Graphics.FromImage(bmp))
        {
            g.CopyFromScreen(captureX, captureY, 0, 0,
                new System.Drawing.Size(window.ClientWidth, window.ClientHeight), CopyPixelOperation.SourceCopy);
        }
        return new CapturedFrame(bmp);'''
if capture.count(old_capture) != 1:
    raise RuntimeError(f"V0.1.7 expected V0.1.6 capture block once, found {capture.count(old_capture)}")
write(capture_path, capture.replace(old_capture, new_capture, 1))

# Hook matching: keep the narrow configured ROI for normal operation, but if its score
# is weak search a wider lower-center region. This heals small client/ROI offsets without
# lowering the audited 0.78 acceptance threshold or removing two-frame confirmation.
matcher_path = app / "TemplateMatcher.cs"
matcher = read(matcher_path)
old_match = '    public MatchResult MatchHook(Mat gray, Rectangle roi) => MatchVariants(gray, roi, _hookVariants);'
new_match = '''    public MatchResult MatchHook(Mat gray, Rectangle roi)
    {
        MatchResult primary = MatchVariants(gray, roi, _hookVariants);
        if (primary.Score >= 0.78) return primary;

        int left = Math.Max(0, (int)Math.Round(gray.Width * 0.18));
        int top = Math.Max(0, (int)Math.Round(gray.Height * 0.68));
        int width = Math.Max(1, gray.Width - (left * 2));
        int height = Math.Max(1, gray.Height - top);
        Rectangle recoveryRoi = new(left, top, width, height);
        MatchResult recovery = MatchVariants(gray, recoveryRoi, _hookVariants);
        return recovery.Score > primary.Score ? recovery : primary;
    }'''
if matcher.count(old_match) != 1:
    raise RuntimeError(f"V0.1.7 expected one MatchHook expression, found {matcher.count(old_match)}")
matcher = matcher.replace(old_match, new_match, 1)

# If an in-place update left an old runtime hook.png behind, recover it from the packaged
# source copy. START.cmd also refreshes the runtime asset, so direct EXE launches and START
# launches both converge on the audited hook image.
if 'using System.Security.Cryptography;' not in matcher:
    matcher = matcher.replace('using OpenCvSharp;\n', 'using OpenCvSharp;\nusing System.Security.Cryptography;\n', 1)
old_ctor = '''        _log = log;
        _hook = LoadGray(Path.Combine(templateDir, "hook.png"), required: true)!;'''
new_ctor = '''        _log = log;
        EnsureCurrentHookTemplate(templateDir);
        _hook = LoadGray(Path.Combine(templateDir, "hook.png"), required: true)!;'''
if matcher.count(old_ctor) != 1:
    raise RuntimeError("V0.1.7 could not insert hook template self-heal")
matcher = matcher.replace(old_ctor, new_ctor, 1)
insert_before = '    private Mat? LoadGray(string path, bool required)\n'
if matcher.count(insert_before) != 1:
    raise RuntimeError("V0.1.7 could not locate TemplateMatcher LoadGray insertion point")
helper = '''    private const string CurrentHookSha256 = "b85d3443d156ec31957a7b24ddeeb507a1c5bbbcbf2d3dad4be8213114b4ce8d";

    private void EnsureCurrentHookTemplate(string templateDir)
    {
        string runtime = Path.Combine(templateDir, "hook.png");
        if (FileHash(runtime) == CurrentHookSha256) return;

        string[] candidates =
        {
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "FishingAutomation", "templates", "hook.png")),
            Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "FishingAutomation", "templates", "hook.png")),
            Path.GetFullPath(Path.Combine(templateDir, "..", "..", "FishingAutomation", "templates", "hook.png"))
        };

        foreach (string candidate in candidates.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            try
            {
                if (!File.Exists(candidate) || FileHash(candidate) != CurrentHookSha256) continue;
                Directory.CreateDirectory(templateDir);
                File.Copy(candidate, runtime, true);
                _log.Write("hook 템플릿 자동 복구: 패키지 현재 이미지로 교체");
                return;
            }
            catch { }
        }

        _log.Write($"경고: hook 템플릿 해시 불일치 - {runtime}");
    }

    private static string FileHash(string path)
    {
        try
        {
            if (!File.Exists(path)) return "";
            return Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
        }
        catch { return ""; }
    }

'''
matcher = matcher.replace(insert_before, helper + insert_before, 1)
write(matcher_path, matcher)

# Force the canonical hook image into release/templates on START. Other templates retain
# the guarded copy behavior so only the known-bad stale hook path is made authoritative.
start_path = root / "START.cmd"
start = read(start_path)
old_hook_guard = 'if not exist "%ROOT%\\release\\templates\\hook.png" '
if start.count(old_hook_guard) != 1:
    raise RuntimeError(f"V0.1.7 expected one guarded hook copy in START.cmd, found {start.count(old_hook_guard)}")
start = start.replace(old_hook_guard, '', 1)
write(start_path, start)

# Preserve the user's 8-second abnormal-state capture rule for the stage that is failing.
bot_path = app / "FishingBot.cs"
bot = read(bot_path)
old_locals = '''        DateTime lastGaugeResync = DateTime.MinValue;
        int hookFrames = 0;
        int compassFrames = 0;'''
new_locals = '''        DateTime lastGaugeResync = DateTime.MinValue;
        Stopwatch stage1Wait = Stopwatch.StartNew();
        bool stage1DebugSaved = false;
        int hookFrames = 0;
        int compassFrames = 0;'''
if bot.count(old_locals) != 1:
    raise RuntimeError("V0.1.7 could not add stage1 wait diagnostics")
bot = bot.replace(old_locals, new_locals, 1)
old_diag = '''                Status($"시전 대기 · Hook {hook.Score:F2} x{hook.Scale:F2}");
                _log.Write($"진단 Hook score={hook.Score:F3}, scale={hook.Scale:F2}, rect={hook.Rect.X},{hook.Rect.Y},{hook.Rect.Width},{hook.Rect.Height}");'''
new_diag = '''                Status($"시전 대기 · Hook {hook.Score:F2} x{hook.Scale:F2}");
                _log.Write($"진단 Hook score={hook.Score:F3}, scale={hook.Scale:F2}, rect={hook.Rect.X},{hook.Rect.Y},{hook.Rect.Width},{hook.Rect.Height}");
                if (!stage1DebugSaved && stage1Wait.Elapsed >= TimeSpan.FromSeconds(8))
                {
                    stage1DebugSaved = true;
                    SaveDebug(f.Bitmap, "stage1_hook_wait_8s");
                    _log.Write($"시전 대기 8초 디버그 저장 · Hook {hook.Score:F3} x{hook.Scale:F2}");
                }'''
if bot.count(old_diag) != 1:
    raise RuntimeError("V0.1.7 could not insert stage1 debug capture")
bot = bot.replace(old_diag, new_diag, 1)
write(bot_path, bot)

# Guard the retained behavior explicitly.
for marker in (
    'double hookThreshold = Math.Min(_cfg.HookThreshold, 0.78);',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도',
):
    if marker not in bot:
        raise RuntimeError(f"V0.1.7 requires retained fishing invariant: {marker}")

config_path = app / "config.json"
config_text = read(config_path)
if '"HookThreshold": 0.78' not in config_text:
    raise RuntimeError("V0.1.7 requires HookThreshold 0.78")

changes = root / "CHANGES_V0.1.7_FISHING_CAPTURE_RESYNC.txt"
changes.write_text(
    "MABI AUTO V0.1.7 - fishing capture position and hook recovery\n"
    "- 22:41 stall report showed the visible Space hook while the bot reported Hook 0.39 x0.65.\n"
    "- CaptureService now refreshes the current client-screen origin with GetClientRect + ClientToScreen for every frame instead of using only the F9-time cached origin.\n"
    "- MatchHook keeps the narrow ROI first, then searches a wider lower-center recovery ROI when the primary score is below 0.78.\n"
    "- START.cmd force-refreshes release/templates/hook.png from the packaged current template; TemplateMatcher also self-heals stale runtime hook assets when the packaged source copy is available.\n"
    "- Stage-1 cast wait saves one debug frame after 8 seconds, matching the abnormal-state capture rule.\n"
    "- V0.1.6 foreground restoration, V0.1.5 0.78/two-frame recognition and live-gauge resync remain enabled.\n",
    encoding="utf-8",
)

tracked = [
    app / "UpdateManager.cs",
    project,
    capture_path,
    matcher_path,
    start_path,
    bot_path,
    app / "FishingFocusGuard.cs",
    app / "NativeMethods.cs",
    app / "MainForm.cs",
    config_path,
    changes,
]
audit = {
    "base_public_version": "V0.1.6",
    "technical_bridge_base": "v79",
    "technical_bridge_tag": "v80",
    "version": "V0.1.7",
    "purpose": "Refresh physical capture coordinates every frame, recover hook search outside the narrow ROI, and prevent stale runtime hook templates",
    "capture_origin": "GetClientRect + ClientToScreen every frame",
    "effective_hook_threshold": 0.78,
    "hook_recovery_roi": "lower-center dynamic 18%-82% width, bottom 32% height",
    "stage1_debug_seconds": 8,
    "hook_template_sha256": "b85d3443d156ec31957a7b24ddeeb507a1c5bbbcbf2d3dad4be8213114b4ce8d",
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
}
(root / "V0_1_7_FISHING_CAPTURE_RESYNC_AUDIT.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V0.1.7 applied: live capture origin refresh + adaptive hook recovery + stale hook self-heal + stage1 8s debug")
