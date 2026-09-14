#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
sidecar = Path(__file__).with_name("v66_dungeon_clear.b64")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"v66 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Version bump. Keep all v65/v64 runtime fixes intact.
# ---------------------------------------------------------------------------
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v65";',
                 'public const string CurrentVersion = "v66";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "66.0.0"), ("AssemblyVersion", "66.0.0.0"), ("FileVersion", "66.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v66 project version tag missing: {name}")
write(project, s)

# ---------------------------------------------------------------------------
# Abyss clear detection: image-only, multi-scale, no rank-S and no OCR.
# The new '던전 클리어' template comes from the user's actual clear screen.
# Existing touch_screen.png is retained as the second visual alternative.
# ---------------------------------------------------------------------------
if not sidecar.is_file():
    raise RuntimeError("v66 dungeon-clear template payload missing")
clear_bytes = base64.b64decode(sidecar.read_text(encoding="ascii").strip(), validate=True)
clear_sha = hashlib.sha256(clear_bytes).hexdigest()
expected_clear_sha = "dd49308bcebb0ebf23d167b6cfb5093ca11c7e677dd2c07629e13a555d97a68e"
if clear_sha != expected_clear_sha:
    raise RuntimeError(f"v66 dungeon-clear template SHA mismatch: {clear_sha}")
clear_template = app / "abyss" / "templates" / "dungeon_clear_v66.png"
clear_template.parent.mkdir(parents=True, exist_ok=True)
clear_template.write_bytes(clear_bytes)

targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(targets_path.read_text(encoding="utf-8-sig"))
# Remove the old OCR title and S-grade fallback completely.
targets = [t for t in targets if t.get("Id") not in {"abyss_dungeon_clear_text", "abyss_clear_grade_s", "abyss_dungeon_clear_visual"}]
touch = [t for t in targets if t.get("Id") == "abyss_touch_screen"]
if len(touch) != 1:
    raise RuntimeError(f"v66 expected one abyss_touch_screen target, found {len(touch)}")
touch = touch[0]
if not touch.get("TemplatePath"):
    raise RuntimeError("v66 abyss_touch_screen template path is missing")
touch["Kind"] = "template"
touch.pop("Text", None)
touch.pop("MaxEditDistance", None)
touch.pop("OcrRetryAt2x", None)
# Preserve the proven v65 touch-screen visual range.
touch["Threshold"] = float(touch.get("Threshold", 0.68))
touch["TemplateScaleMin"] = float(touch.get("TemplateScaleMin", 0.60))
touch["TemplateScaleMax"] = float(touch.get("TemplateScaleMax", 1.55))
touch["TemplateScaleStep"] = float(touch.get("TemplateScaleStep", 0.05))

targets.append({
    "Id": "abyss_dungeon_clear_visual",
    "Kind": "template",
    "Roi": {"X": 120, "Y": 120, "Width": 560, "Height": 300},
    "TemplatePath": "templates/dungeon_clear_v66.png",
    "Threshold": 0.64,
    "TemplateScaleMin": 0.65,
    "TemplateScaleMax": 1.35,
    "TemplateScaleStep": 0.05,
})
targets_path.write_text(json.dumps(targets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

engine_path = app / "dungeon" / "ScenarioEngine.cs"
s = read(engine_path)
s = replace_once(
    s,
    "        bool alternativeClicked = false;\n\n        while (sw.Elapsed < TimeSpan.FromSeconds(step.TimeoutSeconds))",
    "        bool alternativeClicked = false;\n        int abyssClearConsecutive = 0;\n\n        while (sw.Elapsed < TimeSpan.FromSeconds(step.TimeoutSeconds))",
    "Abyss clear consecutive counter",
)
old_clear_branch = '''            // Abyss clear screen must win over the global scene-skip monitor.\n            // v29 had no scene-skip monitor and did not miss this screen.\n            // Keep all other steps on the existing monitor-first behavior.\n            DetectionResult found;\n            if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))\n            {\n                // Clear screen can appear before the touch prompt is reliably recognized.\n                // Prefer the clear title / large S grade, then fall back to the existing\n                // "화면을 터치해 주세요" target.\n                found = await _detector.DetectAsync("abyss_dungeon_clear_text", frame, ct);\n                if (!found.Found)\n                    found = await _detector.DetectAsync("abyss_clear_grade_s", frame, ct);\n                if (!found.Found)\n                    found = await _detector.DetectAsync(step.Target, frame, ct);\n\n                if (!found.Found && await CheckMonitorsAsync(frame, ct))\n                    continue;\n            }\n            else\n            {\n                if (await CheckMonitorsAsync(frame, ct))\n                    continue;\n                found = await _detector.DetectAsync(step.Target, frame, ct);\n            }'''
new_clear_branch = '''            // Abyss clear screen must win over the global scene-skip monitor.\n            // v66: image-only multi-scale confirmation. Rank S and OCR are not used.\n            DetectionResult found;\n            if (step.Target.Equals("abyss_touch_screen", StringComparison.OrdinalIgnoreCase))\n            {\n                found = await DetectAbyssClearVisualAsync(frame, ct);\n                if (!found.Found)\n                {\n                    abyssClearConsecutive = 0;\n                    if (await CheckMonitorsAsync(frame, ct))\n                        continue;\n                }\n                else\n                {\n                    abyssClearConsecutive++;\n                    Log?.Invoke($"[어비스] 클리어 이미지 연속 확인 {abyssClearConsecutive}/2");\n                    if (abyssClearConsecutive < 2)\n                    {\n                        await Task.Delay(Math.Max(150, _settings.PollIntervalMs), ct);\n                        continue;\n                    }\n                    abyssClearConsecutive = 0;\n                }\n            }\n            else\n            {\n                if (await CheckMonitorsAsync(frame, ct))\n                    continue;\n                found = await _detector.DetectAsync(step.Target, frame, ct);\n            }'''
s = replace_once(s, old_clear_branch, new_clear_branch, "Abyss clear detection branch")

old_advance = '''    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)\n    {\n        Log?.Invoke("[어비스] 클리어 화면 감지 -> 1차 클릭");\n        _input.ClickClientPoint(_hwnd, firstDetection.Center);\n        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);\n\n        using (var afterFirst = await CaptureGameWindowAsync(ct))\n        {\n            var touchStillVisible = await _detector.DetectAsync("abyss_touch_screen", afterFirst, ct);\n            if (!touchStillVisible.Found)\n            {\n                Log?.Invoke("[어비스] 1차 클릭 후 클리어 화면 전환 확인");\n                return;\n            }\n\n            Log?.Invoke("[어비스] '화면을 터치해 주세요' 유지 -> 2차 클릭");\n            _input.ClickClientPoint(_hwnd, touchStillVisible.Center);\n        }\n\n        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);\n\n        using var afterSecond = await CaptureGameWindowAsync(ct);\n        var touchAfterSecond = await _detector.DetectAsync("abyss_touch_screen", afterSecond, ct);\n        if (touchAfterSecond.Found)\n        {\n            Log?.Invoke("[어비스] 경고: 2회 클릭 후에도 '화면을 터치해 주세요'가 남아 있음");\n            throw new TimeoutException("어비스 클리어 화면이 2회 클릭 후에도 넘어가지 않았습니다.");\n        }\n\n        Log?.Invoke("[어비스] 2차 클릭 후 클리어 화면 전환 확인");\n    }'''
new_advance = '''    private async Task<DetectionResult> DetectAbyssClearVisualAsync(Bitmap frame, CancellationToken ct)\n    {\n        var clearTitle = await _detector.DetectAsync("abyss_dungeon_clear_visual", frame, ct);\n        if (clearTitle.Found) return clearTitle;\n        return await _detector.DetectAsync("abyss_touch_screen", frame, ct);\n    }\n\n    private async Task AdvanceAbyssClearScreenAsync(DetectionResult firstDetection, CancellationToken ct)\n    {\n        Log?.Invoke("[어비스] 클리어 화면 이미지 2회 확인 완료 -> 1차 클릭");\n        _input.ClickClientPoint(_hwnd, firstDetection.Center);\n        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);\n\n        using (var afterFirst = await CaptureGameWindowAsync(ct))\n        {\n            var clearStillVisible = await DetectAbyssClearVisualAsync(afterFirst, ct);\n            if (!clearStillVisible.Found)\n            {\n                Log?.Invoke("[어비스] 1차 클릭 후 클리어 화면 전환 확인");\n                return;\n            }\n\n            Log?.Invoke("[어비스] 클리어 화면 유지 -> 2차 클릭");\n            _input.ClickClientPoint(_hwnd, clearStillVisible.Center);\n        }\n\n        await Task.Delay(Math.Max(1000, _settings.ClickSettleMs), ct);\n\n        using var afterSecond = await CaptureGameWindowAsync(ct);\n        var clearAfterSecond = await DetectAbyssClearVisualAsync(afterSecond, ct);\n        if (clearAfterSecond.Found)\n        {\n            Log?.Invoke("[어비스] 경고: 2회 클릭 후에도 클리어 화면 이미지가 남아 있음");\n            throw new TimeoutException("어비스 클리어 화면이 2회 클릭 후에도 넘어가지 않았습니다.");\n        }\n\n        Log?.Invoke("[어비스] 2차 클릭 후 클리어 화면 전환 확인");\n    }'''
s = replace_once(s, old_advance, new_advance, "Abyss clear advance method")
write(engine_path, s)

# ---------------------------------------------------------------------------
# Scheduled safe stop. This calls the exact same StopSelected() path used by F10.
# Settings live in LocalAppData so updater replacement does not erase them.
# ---------------------------------------------------------------------------
main_path = app / "MainForm.cs"
s = read(main_path)
s = replace_once(
    s,
    "    private readonly System.Windows.Forms.Timer _uiTimer = new() { Interval = 500 };\n",
    "    private readonly System.Windows.Forms.Timer _uiTimer = new() { Interval = 500 };\n"
    "    private bool _autoStopEnabled;\n"
    "    private TimeSpan _autoStopTime = new(2, 30, 0);\n"
    "    private DateTime? _autoStopLastTriggeredDate;\n"
    "    private string _autoStopSettingsPath = \"\";\n",
    "auto-stop fields",
)
s = replace_once(
    s,
    "        _fishingBot = new FishingBot(cfg, _log);\n\n        Text = \"Mabi_Auto\";",
    "        _fishingBot = new FishingBot(cfg, _log);\n"
    "        LoadAutoStopSettings();\n\n"
    "        Text = \"Mabi_Auto\";",
    "auto-stop settings load",
)
s = replace_once(
    s,
    "        _uiTimer.Tick += (_, _) => { _watchdog.Touch(); CheckAlertHealth(); UpdateStats(); };",
    "        _uiTimer.Tick += (_, _) => { _watchdog.Touch(); CheckAlertHealth(); CheckAutoStop(); UpdateStats(); };",
    "auto-stop timer check",
)
methods = '''    private void LoadAutoStopSettings()\n    {\n        try\n        {\n            string dir = Path.Combine(\n                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),\n                "MabiAuto");\n            _autoStopSettingsPath = Path.Combine(dir, "auto-stop.json");\n            if (!File.Exists(_autoStopSettingsPath)) return;\n\n            using var doc = JsonDocument.Parse(File.ReadAllText(_autoStopSettingsPath));\n            var rootNode = doc.RootElement;\n            if (rootNode.TryGetProperty("Enabled", out var enabled) &&\n                (enabled.ValueKind == JsonValueKind.True || enabled.ValueKind == JsonValueKind.False))\n                _autoStopEnabled = enabled.GetBoolean();\n\n            if (rootNode.TryGetProperty("Time", out var timeNode))\n            {\n                string? value = timeNode.GetString();\n                string[] parts = (value ?? "").Split(':');\n                if (parts.Length == 2 && int.TryParse(parts[0], out int hour) &&\n                    int.TryParse(parts[1], out int minute) &&\n                    hour is >= 0 and <= 23 && minute is >= 0 and <= 59)\n                    _autoStopTime = new TimeSpan(hour, minute, 0);\n            }\n        }\n        catch { }\n    }\n\n    private void SaveAutoStopSettings()\n    {\n        try\n        {\n            if (string.IsNullOrWhiteSpace(_autoStopSettingsPath))\n            {\n                string dir = Path.Combine(\n                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),\n                    "MabiAuto");\n                _autoStopSettingsPath = Path.Combine(dir, "auto-stop.json");\n            }\n            Directory.CreateDirectory(Path.GetDirectoryName(_autoStopSettingsPath)!);\n            var data = new\n            {\n                Enabled = _autoStopEnabled,\n                Time = $"{(int)_autoStopTime.TotalHours:00}:{_autoStopTime.Minutes:00}"\n            };\n            File.WriteAllText(_autoStopSettingsPath,\n                JsonSerializer.Serialize(data, new JsonSerializerOptions { WriteIndented = true }));\n        }\n        catch { }\n    }\n\n    private void SetAutoStopEnabled(bool enabled)\n    {\n        _autoStopEnabled = enabled;\n        SaveAutoStopSettings();\n    }\n\n    private void SetAutoStopTime(DateTime value)\n    {\n        _autoStopTime = new TimeSpan(value.Hour, value.Minute, 0);\n        SaveAutoStopSettings();\n    }\n\n    private void CheckAutoStop()\n    {\n        if (!_autoStopEnabled || !AnyRunning) return;\n        DateTime now = DateTime.Now;\n        if (now.Hour != _autoStopTime.Hours || now.Minute != _autoStopTime.Minutes) return;\n        if (_autoStopLastTriggeredDate?.Date == now.Date) return;\n\n        _autoStopLastTriggeredDate = now.Date;\n        _log.Write($"[자동 정지] 예약 시간 {now:HH:mm} 도달 -> F10과 동일한 안전 정지");\n        StopSelected();\n    }\n\n'''
s = replace_once(s, "    private void StopSelected()\n", methods + "    private void StopSelected()\n", "auto-stop methods insertion")
write(main_path, s)

# ---------------------------------------------------------------------------
# HOME reference dashboard only: compact auto-stop control in the banner's
# top-right area, immediately above the System Status panel. No other window,
# panel, card, button, or layout is moved/resized.
# ---------------------------------------------------------------------------
ui_path = app / "MainForm.ReferenceUI.cs"
s = read(ui_path)
s = replace_once(s, 'TextAt(g, "v65.0.0 · UI", new(252, 22, 150, 35), 15);',
                 'TextAt(g, "v66.0.0 · UI", new(252, 22, 150, 35), 15);', 'reference UI version')
ui_insert = '''            BackColor = Color.FromArgb(0, 16, 31);\n\n            // v66: HOME-only scheduled stop control. This deliberately occupies unused\n            // banner space above the System Status card and does not move existing UI.\n            var autoStopCheck = new CheckBox\n            {\n                Text = "자동 정지",\n                AccessibleName = "자동 정지 사용",\n                Checked = owner._autoStopEnabled,\n                AutoSize = false,\n                FlatStyle = FlatStyle.Flat,\n                BackColor = Color.FromArgb(2, 22, 42),\n                ForeColor = _text,\n                Font = new Font("맑은 고딕", 11f, FontStyle.Bold),\n                TextAlign = ContentAlignment.MiddleLeft,\n                Cursor = Cursors.Hand\n            };\n            var autoStopTime = new DateTimePicker\n            {\n                AccessibleName = "자동 정지 시간",\n                Format = DateTimePickerFormat.Custom,\n                CustomFormat = "HH:mm",\n                ShowUpDown = true,\n                Value = DateTime.Today.Add(owner._autoStopTime),\n                Font = new Font("맑은 고딕", 11f, FontStyle.Bold),\n                CalendarForeColor = Color.White,\n                CalendarMonthBackground = Color.FromArgb(3, 29, 51)\n            };\n            autoStopCheck.CheckedChanged += (_, _) => owner.SetAutoStopEnabled(autoStopCheck.Checked);\n            autoStopTime.ValueChanged += (_, _) => owner.SetAutoStopTime(autoStopTime.Value);\n            Controls.Add(autoStopCheck);\n            Controls.Add(autoStopTime);\n            var autoStopCheckBounds = new RectangleF(1080, 159, 128, 48);\n            var autoStopTimeBounds = new RectangleF(1212, 159, 178, 48);\n            _positions.Add((autoStopCheck, autoStopCheckBounds));\n            _positions.Add((autoStopTime, autoStopTimeBounds));\n            autoStopCheck.Bounds = Rectangle.Round(new RectangleF(autoStopCheckBounds.X * ScaleX, autoStopCheckBounds.Y * ScaleY, autoStopCheckBounds.Width * ScaleX, autoStopCheckBounds.Height * ScaleY));\n            autoStopTime.Bounds = Rectangle.Round(new RectangleF(autoStopTimeBounds.X * ScaleX, autoStopTimeBounds.Y * ScaleY, autoStopTimeBounds.Width * ScaleX, autoStopTimeBounds.Height * ScaleY));\n\n'''
s = replace_once(s, "            BackColor = Color.FromArgb(0, 16, 31);\n\n", ui_insert, "home auto-stop controls")
write(ui_path, s)

changes = root / "CHANGES_v66_ABYSS_CLEAR_AUTOSTOP.txt"
changes.write_text(
    "MABI AUTO v66\n"
    "- Abyss clear detection: image-only multi-scale, using '던전 클리어' OR existing '화면을 터치해 주세요'.\n"
    "- Rank S and OCR are not used for Abyss clear detection.\n"
    "- A clear screen must be visually detected twice consecutively before the normal clear-click flow runs.\n"
    "- Home dashboard only: compact scheduled auto-stop control added above System Status.\n"
    "- Scheduled stop uses the existing F10/StopSelected safe-stop path and persists under LocalAppData.\n"
    "- No other window/layout is moved or redesigned.\n"
    "- v65 popup-close visual-only guard and existing scene-skip, treasure, recovery, retry, resize/admin behavior are retained.\n",
    encoding="utf-8",
)

modified = [update, project, targets_path, clear_template, engine_path, main_path, ui_path, changes]
audit = {
    "base": "v65",
    "version": "v66",
    "purpose": "Abyss image-only clear confirmation plus HOME-only scheduled safe stop",
    "abyss_clear": {
        "mode": "template-only multi-scale",
        "alternatives": ["abyss_dungeon_clear_visual", "abyss_touch_screen"],
        "consecutive_required": 2,
        "rank_s_used": False,
        "ocr_used": False,
        "dungeon_clear_template_sha256": clear_sha,
        "dungeon_clear_scale": [0.65, 1.35, 0.05],
    },
    "auto_stop": {
        "ui_scope": "ReferenceDashboard HOME only; top banner above System Status",
        "safe_stop_path": "StopSelected (same path as F10)",
        "persistent": "LocalAppData/MabiAuto/auto-stop.json",
    },
    "preserved": [
        "v65 abyss_popup_close template-only guard",
        "scene_skip", "treasure chest", "normal exit", "Smart Recovery", "retry",
        "administrator elevation", "exact 800x1000 sizing", "dual-monitor handling"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V66_ABYSS_CLEAR_AUTOSTOP_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("v66 applied: Abyss visual clear guard + HOME-only scheduled safe stop")
