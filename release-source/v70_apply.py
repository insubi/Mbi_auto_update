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
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"v70 expected exactly one {label}, found {count}")
    return text.replace(old, new, 1)


# Require the published v69 source so all Telegram/Abyss/UI changes stay intact.
v69_audit_path = root / "V69_UI_ABYSS_AUDIT.json"
if not v69_audit_path.is_file():
    raise RuntimeError("v69 audit missing; v70 must be applied on v69 source")
v69_audit = json.loads(v69_audit_path.read_text(encoding="utf-8-sig"))
if v69_audit.get("version") != "v69":
    raise RuntimeError("unexpected base audit version")

# Version bump only outside the HOME scheduled-stop visual block.
update = app / "UpdateManager.cs"
s = read(update)
s = replace_once(s, 'public const string CurrentVersion = "v69";',
                 'public const string CurrentVersion = "v70";', 'UpdateManager version')
write(update, s)

project = app / "FishingAutomation.csproj"
s = read(project)
for name, value in (("Version", "70.0.0"), ("AssemblyVersion", "70.0.0.0"), ("FileVersion", "70.0.0.0")):
    pattern = fr"<{name}>[^<]+</{name}>"
    s, count = re.subn(pattern, f"<{name}>{value}</{name}>", s, count=1)
    if count != 1:
        raise RuntimeError(f"v70 project version tag missing: {name}")
write(project, s)

ui_path = app / "MainForm.ReferenceUI.cs"
s = read(ui_path)
s = replace_once(s, 'TextAt(g, "v69", new(244, 20, 70, 37), 15, true, _cyan);',
                 'TextAt(g, "v70", new(244, 20, 70, 37), 15, true, _cyan);', 'reference UI version')

# Replace only the v69 scheduled-stop native controls. The separate label + large-font
# DateTimePicker caused the caption to clip and the white Windows control to visually clash
# with the custom-painted HOME dashboard at the user's normal ~65% window scale.
pattern = re.compile(
    r'''            // v66: HOME-only scheduled stop control\..*?'''
    r'''            autoStopTime\.Bounds = Rectangle\.Round\(new RectangleF\(autoStopTimeBounds\.X \* ScaleX, autoStopTimeBounds\.Y \* ScaleY, autoStopTimeBounds\.Width \* ScaleX, autoStopTimeBounds\.Height \* ScaleY\)\);\n''',
    re.S,
)
new_block = '''            // v70: HOME-only scheduled stop control. Keep it in the unused top-banner area,
            // use one full caption and a dark masked time field so it visually matches the
            // custom-painted dashboard instead of looking like a separate Windows widget.
            var autoStopCheck = new CheckBox
            {
                Text = "자동 정지",
                AccessibleName = "자동 정지",
                Checked = owner._autoStopEnabled,
                AutoSize = false,
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(2, 22, 42),
                ForeColor = _text,
                Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Bold, GraphicsUnit.Point),
                CheckAlign = ContentAlignment.MiddleLeft,
                TextAlign = ContentAlignment.MiddleLeft,
                Cursor = Cursors.Hand,
                Padding = new Padding(0, 0, 0, 1)
            };
            autoStopCheck.FlatAppearance.BorderSize = 0;

            var autoStopTime = new MaskedTextBox("00:00")
            {
                AccessibleName = "자동 정지 시간",
                Text = $"{owner._autoStopTime.Hours:00}:{owner._autoStopTime.Minutes:00}",
                TextAlign = HorizontalAlignment.Center,
                BackColor = Color.FromArgb(3, 29, 51),
                ForeColor = Color.White,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font(_baseFont.FontFamily, 9.5f, FontStyle.Bold, GraphicsUnit.Point),
                PromptChar = ' ',
                HidePromptOnLeave = false,
                InsertKeyMode = InsertKeyMode.Overwrite,
                RejectInputOnFirstFailure = true,
                ShortcutsEnabled = true,
                AutoSize = false
            };

            void CommitAutoStopTime()
            {
                string[] parts = autoStopTime.Text.Trim().Split(':');
                if (parts.Length == 2 && int.TryParse(parts[0], out int hour) &&
                    int.TryParse(parts[1], out int minute) &&
                    hour is >= 0 and <= 23 && minute is >= 0 and <= 59)
                {
                    owner.SetAutoStopTime(DateTime.Today.AddHours(hour).AddMinutes(minute));
                    autoStopTime.Text = $"{hour:00}:{minute:00}";
                }
                else
                {
                    autoStopTime.Text = $"{owner._autoStopTime.Hours:00}:{owner._autoStopTime.Minutes:00}";
                }
            }

            autoStopCheck.CheckedChanged += (_, _) => owner.SetAutoStopEnabled(autoStopCheck.Checked);
            autoStopTime.Leave += (_, _) => CommitAutoStopTime();
            autoStopTime.KeyDown += (_, e) =>
            {
                if (e.KeyCode != Keys.Enter) return;
                CommitAutoStopTime();
                e.SuppressKeyPress = true;
            };
            autoStopTime.GotFocus += (_, _) =>
                autoStopTime.BeginInvoke(new Action(autoStopTime.SelectAll));

            Controls.Add(autoStopCheck);
            Controls.Add(autoStopTime);

            // At the normal 0.65 HOME scale these become roughly 104px + 86px wide,
            // enough for the complete caption and HH:mm without touching nearby cards.
            var autoStopCheckBounds = new RectangleF(1068, 154, 160, 48);
            var autoStopTimeBounds = new RectangleF(1240, 154, 132, 48);
            _positions.Add((autoStopCheck, autoStopCheckBounds));
            _positions.Add((autoStopTime, autoStopTimeBounds));
            autoStopCheck.Bounds = Rectangle.Round(new RectangleF(autoStopCheckBounds.X * ScaleX, autoStopCheckBounds.Y * ScaleY, autoStopCheckBounds.Width * ScaleX, autoStopCheckBounds.Height * ScaleY));
            autoStopTime.Bounds = Rectangle.Round(new RectangleF(autoStopTimeBounds.X * ScaleX, autoStopTimeBounds.Y * ScaleY, autoStopTimeBounds.Width * ScaleX, autoStopTimeBounds.Height * ScaleY));
'''
s, count = pattern.subn(new_block, s, count=1)
if count != 1:
    raise RuntimeError(f"v70 scheduled-stop UI block not found exactly once: {count}")
write(ui_path, s)

changes_path = root / "CHANGES_v70_AUTOSTOP_UI.txt"
changes_path.write_text(
    "MABI AUTO v70\n"
    "- HOME scheduled-stop caption now displays the full '자동 정지' text in one control.\n"
    "- Scheduled-stop caption/time use the same Malgun Gothic family and compact size as the dashboard.\n"
    "- The bright native DateTimePicker was replaced with a dark HH:mm MaskedTextBox.\n"
    "- Checkbox + caption + time remain on one line in the top-right banner with extra width so Korean text does not clip.\n"
    "- Time validation remains 00:00-23:59 and settings still persist through the existing auto-stop settings code.\n"
    "- F10-safe stop behavior, Telegram UI, Abyss dungeon previews, clear flow/recovery, all other windows and layouts are unchanged.\n",
    encoding="utf-8",
)

modified = [update, project, ui_path, changes_path]
audit = {
    "base": "v69",
    "version": "v70",
    "purpose": "Polish HOME scheduled-stop control without changing runtime behavior",
    "auto_stop_ui": {
        "caption": "자동 정지",
        "caption_clipping_fixed": True,
        "font_family": "맑은 고딕",
        "font_size_points": 9.5,
        "time_control": "MaskedTextBox",
        "time_format": "HH:mm",
        "dark_time_background": True,
        "one_line_layout": True,
        "safe_stop_path_preserved": "StopSelected",
        "settings_persistence_preserved": True,
    },
    "preserved": [
        "v69 HOME title/sidebar/Telegram dialog",
        "v69 Abyss dungeon preview images",
        "v69 Abyss clear transition and in-dungeon recovery",
        "F10 manual safe stop",
        "other windows and layouts",
        "administrator elevation",
        "exact 800x1000 game-window sizing and monitor placement"
    ],
    "files": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in modified},
}
(root / "V70_AUTOSTOP_UI_AUDIT.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print("v70 applied: full auto-stop caption + matching font + dark HH:mm field")
