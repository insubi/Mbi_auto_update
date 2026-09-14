#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig")

def replace_once(path: Path, old: str, new: str) -> None:
    s = read_text(path)
    if old not in s:
        raise RuntimeError(f"required pattern missing in {path}: {old[:120]}")
    write_text(path, s.replace(old, new, 1))

# v49 is UI-only. Verify v48 runtime features stay present.
main_form = read_text(app / "MainForm.cs")
if "WatchdogClient" not in main_form or "_watchdog.Touch()" not in main_form:
    raise RuntimeError("watchdog integration missing")
if "CheckForUpdatesAsync(false)" not in main_form:
    raise RuntimeError("automatic update check missing")

update_manager = read_text(app / "UpdateManager.cs")
if 'public const string CurrentVersion = "v48";' not in update_manager:
    raise RuntimeError("v48 base not found")
for marker in ("CheckLatestAsync", "DownloadAsync", "LaunchUpdater", "MarkStartupHealthy"):
    if marker not in update_manager:
        raise RuntimeError(f"updater marker missing: {marker}")

targets = json.loads(read_text(app / "abyss" / "config" / "targets.json"))
if not any(t.get("Id") == "abyss_popup_close" for t in targets):
    raise RuntimeError("potion popup close target missing")
scenario = json.loads(read_text(app / "abyss" / "config" / "scenario.json"))
if "abyss_popup_close" not in json.dumps(scenario, ensure_ascii=False):
    raise RuntimeError("potion popup close monitor missing")

# Version / window geometry only.
replace_once(app / "UpdateManager.cs", 'public const string CurrentVersion = "v48";', 'public const string CurrentVersion = "v49";')
replace_once(app / "MainForm.cs", "Width = 1320;", "Width = 1360;")
replace_once(app / "MainForm.cs", "Height = 900;", "Height = 940;")
replace_once(app / "MainForm.cs", "MinimumSize = new Size(1180, 800);", "MinimumSize = new Size(1220, 820);")

p = app / "MainForm.Dashboard.cs"
s = read_text(p)

# Header: prevent the top chips/brand from being vertically clipped on DPI-scaled displays.
s = s.replace('root.RowStyles.Add(new RowStyle(SizeType.Absolute, 70));', 'root.RowStyles.Add(new RowStyle(SizeType.Absolute, 88));', 1)
s = s.replace('var header = new Panel { Dock = DockStyle.Fill, BackColor = NavBg, Padding = new Padding(22, 10, 18, 10) };',
              'var header = new Panel { Dock = DockStyle.Fill, BackColor = NavBg, Padding = new Padding(22, 8, 18, 8) };', 1)
s = s.replace('Text = "v48.0.0"', 'Text = "v49.0.0"', 1)
s = s.replace('label.Font = new Font("맑은 고딕", 8.7f, FontStyle.Bold);', 'label.Font = new Font("맑은 고딕", 8.3f, FontStyle.Bold);', 1)

# Give the system-status column substantially more width.
s = s.replace('grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 76));\n        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 24));',
              'grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 70));\n        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 30));', 1)

# Slightly more vertical room for banner/info while preserving the rest of the dashboard.
s = s.replace('grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 126));', 'grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 132));', 1)
s = s.replace('grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 92));', 'grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 96));', 1)

# Banner: remove the small portrait look by making the image area wider and fill it edge-to-edge.
s = s.replace('layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 68));\n        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 32));',
              'layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 64));\n        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 36));', 1)
s = s.replace('var picture = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.FromArgb(7, 27, 48), Margin = new Padding(8, 2, 2, 2) };',
              'var picture = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.StretchImage, BackColor = Color.FromArgb(7, 27, 48), Margin = new Padding(8, 2, 2, 2) };', 1)

# System status card: tighter inner padding + a safer caption/value split.
s = s.replace('var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 9, Padding = new Padding(12, 9, 12, 9) };',
              'var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 9, Padding = new Padding(8, 9, 8, 9) };', 1)
s = s.replace('row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 66));\n        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 34));',
              'row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 62));\n        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 38));', 1)
s = s.replace('Font = new Font("맑은 고딕", 8f), TextAlign = ContentAlignment.MiddleLeft }, 0, 0);',
              'Font = new Font("맑은 고딕", 7.8f), TextAlign = ContentAlignment.MiddleLeft, AutoEllipsis = false }, 0, 0);', 1)
s = s.replace('value.Font = new Font("맑은 고딕", 8.3f, FontStyle.Bold);',
              'value.Font = new Font("맑은 고딕", 8.0f, FontStyle.Bold);', 1)

# Dungeon visual cards: use the available art as a wide thumbnail instead of a tiny centered portrait.
s = s.replace('inner.RowStyles.Add(new RowStyle(SizeType.Percent, 55));', 'inner.RowStyles.Add(new RowStyle(SizeType.Percent, 64));', 1)
s = s.replace('inner.RowStyles.Add(new RowStyle(SizeType.Absolute, 29));', 'inner.RowStyles.Add(new RowStyle(SizeType.Absolute, 27));', 1)
s = s.replace('inner.RowStyles.Add(new RowStyle(SizeType.Absolute, 24));', 'inner.RowStyles.Add(new RowStyle(SizeType.Absolute, 21));', 1)
s = s.replace('inner.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));', 'inner.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));', 1)
s = s.replace('var picture = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.FromArgb(5, 19, 34), Cursor = Cursors.Hand };',
              'var picture = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.StretchImage, BackColor = Color.FromArgb(5, 19, 34), Cursor = Cursors.Hand, Margin = new Padding(0, 0, 0, 4) };', 1)

# Mini-mode return geometry must match the new full-size minimum.
s = s.replace('MinimumSize = new Size(1180, 800);', 'MinimumSize = new Size(1220, 820);', 1)

write_text(p, s)

# Windows assembly/file version only.
proj = app / "FishingAutomation.csproj"
s = read_text(proj)
for key, value in {
    "Version": "49.0.0",
    "AssemblyVersion": "49.0.0.0",
    "FileVersion": "49.0.0.0",
}.items():
    pat = rf'<{key}>[^<]+</{key}>'
    repl = f'<{key}>{value}</{key}>'
    if re.search(pat, s):
        s = re.sub(pat, repl, s, count=1)
    else:
        s = s.replace("<PropertyGroup>", "<PropertyGroup>\n    " + repl, 1)
write_text(proj, s)

(root / "CHANGES_v49_UI_FIX.txt").write_text(
    "Mabi_Auto v49 UI correction\n"
    "- v48/v46 automation logic unchanged\n"
    "- Fix top header/status-chip clipping\n"
    "- Widen system-status card and prevent Korean labels from clipping\n"
    "- Increase dashboard spacing and usable window height\n"
    "- Enlarge dungeon visual thumbnails\n"
    "- Potion popup close remains background-only\n",
    encoding="utf-8"
)

print("v49 UI correction applied; gameplay/scenario logic unchanged")
