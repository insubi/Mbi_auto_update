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
    text = read_text(path)
    if old not in text:
        raise RuntimeError(f"required pattern missing in {path}: {old[:120]}")
    write_text(path, text.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Safety checks: v47 MUST keep the working v46 runtime features unchanged.
# ---------------------------------------------------------------------------
main_form = read_text(app / "MainForm.cs")
if "WatchdogClient" not in main_form or "_watchdog.Touch()" not in main_form:
    raise RuntimeError("v46 watchdog integration was not found")
if "CheckForUpdatesAsync(false)" not in main_form:
    raise RuntimeError("v46 automatic update check was not found")

update_manager = read_text(app / "UpdateManager.cs")
for marker in ("CheckLatestAsync", "DownloadAsync", "LaunchUpdater", "MarkStartupHealthy"):
    if marker not in update_manager:
        raise RuntimeError(f"v46 updater marker missing: {marker}")

targets_path = app / "abyss" / "config" / "targets.json"
targets = json.loads(read_text(targets_path))
if not any(t.get("Id") == "abyss_popup_close" for t in targets):
    raise RuntimeError("v46 potion-shortage popup close target was not found")

scenario_path = app / "abyss" / "config" / "scenario.json"
scenario = json.loads(read_text(scenario_path))
monitor_dump = json.dumps(scenario, ensure_ascii=False)
if "abyss_popup_close" not in monitor_dump:
    raise RuntimeError("v46 potion-shortage popup monitor was not found")

# ---------------------------------------------------------------------------
# Version / window title only. No automation state-machine logic is changed.
# ---------------------------------------------------------------------------
replace_once(
    app / "UpdateManager.cs",
    'public const string CurrentVersion = "v46";',
    'public const string CurrentVersion = "v47";'
)

replace_once(
    app / "MainForm.cs",
    'Text = "MABI AUTO · v46";',
    'Text = "Mabi_Auto";'
)

# Slightly taller dashboard for the new dungeon-art row.
replace_once(app / "MainForm.cs", "Height = 720;", "Height = 760;")
replace_once(app / "MainForm.cs", "MinimumSize = new Size(1020, 680);", "MinimumSize = new Size(1020, 720);")

# ---------------------------------------------------------------------------
# Dashboard-only redesign. Existing buttons/events/automation calls are reused.
# ---------------------------------------------------------------------------
p = app / "MainForm.Dashboard.cs"
s = read_text(p)

s = s.replace(
    "    private readonly List<Button> _dungeonButtons = new();\n",
    "    private readonly List<Button> _dungeonButtons = new();\n"
    "    private readonly List<Panel> _dungeonCards = new();\n",
    1,
)
s = s.replace(
    "    private readonly Label _sysInputValue = new();\n",
    "    private readonly Label _sysInputValue = new();\n"
    "    private readonly Label _sysWatchdogValue = new();\n",
    1,
)
s = s.replace(
    "    private Control _dungeonPicker = null!;\n",
    "    private Control _dungeonPicker = null!;\n"
    "    private Control _dungeonGallery = null!;\n",
    1,
)

# Branding.
s = s.replace('Text = "MABI AUTO",', 'Text = "Mabi_Auto",', 1)
s = s.replace(
    'Text = "마비노기 모바일 매크로  ·  Dashboard v46",',
    'Text = "Dashboard  ·  v47  ·  v46 안정 로직",',
    1,
)
s = s.replace('Text = "v46  |  Mabi Auto"', 'Text = "v47  |  Mabi_Auto"', 1)

# Sidebar: mode-centric navigation while keeping the same existing mode selector.
old_sidebar = '''        menu.Controls.Add(NavButton("⌂   홈", () => { }, true), 0, 0);
        menu.Controls.Add(NavButton("⚔   던전 설정", () => OpenPackagePath(Path.Combine("FishingAutomation", "abyss", "config"))), 0, 1);
        menu.Controls.Add(NavButton("▣   이미지 설정", () => OpenPackagePath(Path.Combine("FishingAutomation", "abyss", "templates"))), 0, 2);
        menu.Controls.Add(NavButton("➤   텔레그램 알림", OpenPhoneAlertSetup), 0, 3);
        menu.Controls.Add(NavButton("▤   로그", OpenLogFolder), 0, 4);
        menu.Controls.Add(NavButton("⚙   설정", () => OpenPackagePath(Path.Combine("FishingAutomation", "config.json"))), 0, 5);'''
new_sidebar = '''        menu.Controls.Add(NavButton("⌂   홈", () => { }, true), 0, 0);
        menu.Controls.Add(NavButton("●   낚시", () => { if (!AnyRunning && _activeMode is null) _mode.SelectedIndex = 0; }), 0, 1);
        menu.Controls.Add(NavButton("◆   던전", () => { if (!AnyRunning && _activeMode is null) _mode.SelectedIndex = 1; }), 0, 2);
        menu.Controls.Add(NavButton("◈   어비스", () => { if (!AnyRunning && _activeMode is null) _mode.SelectedIndex = 2; }), 0, 3);
        menu.Controls.Add(NavButton("▤   로그 폴더", OpenLogFolder), 0, 4);
        menu.Controls.Add(NavButton("⚙   설정", () => OpenPackagePath(Path.Combine("FishingAutomation", "config.json"))), 0, 5);'''
if old_sidebar not in s:
    raise RuntimeError("v46 sidebar block not found")
s = s.replace(old_sidebar, new_sidebar, 1)

# Make the dashboard three rows and reserve the bottom row for dungeon art cards.
s = s.replace("            RowCount = 2,", "            RowCount = 3,", 1)
old_rows = '''        _dashboard.RowStyles.Add(new RowStyle(SizeType.Percent, 47));
        _dashboard.RowStyles.Add(new RowStyle(SizeType.Percent, 53));'''
new_rows = '''        _dashboard.RowStyles.Add(new RowStyle(SizeType.Percent, 34));
        _dashboard.RowStyles.Add(new RowStyle(SizeType.Percent, 38));
        _dashboard.RowStyles.Add(new RowStyle(SizeType.Percent, 28));'''
if old_rows not in s:
    raise RuntimeError("v46 dashboard row styles not found")
s = s.replace(old_rows, new_rows, 1)

old_grid_tail = '''        _dashboard.Controls.Add(BuildSystemStatusCard(), 2, 1);
        return _dashboard;'''
new_grid_tail = '''        _dashboard.Controls.Add(BuildSystemStatusCard(), 2, 1);
        var gallery = BuildAbyssDungeonGallery();
        _dashboard.Controls.Add(gallery, 0, 2);
        _dashboard.SetColumnSpan(gallery, 3);
        return _dashboard;'''
if old_grid_tail not in s:
    raise RuntimeError("v46 dashboard grid tail not found")
s = s.replace(old_grid_tail, new_grid_tail, 1)

# New visual dungeon selector. It reuses the same _abyssDungeon ComboBox selection,
# so no Abyss navigation/click logic is changed.
gallery_method = r'''
    private Control BuildAbyssDungeonGallery()
    {
        var card = CreateCard();
        card.Margin = new Padding(6);
        _dungeonGallery = card;

        var outer = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 2,
            Padding = new Padding(12, 6, 12, 10)
        };
        outer.RowStyles.Add(new RowStyle(SizeType.Absolute, 30));
        outer.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        outer.Controls.Add(SectionTitle("어비스 던전 선택"), 0, 0);

        var row = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3, RowCount = 1 };
        for (int i = 0; i < 3; i++) row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 33.333f));

        string[] names = { "허상의 정박지", "광기의 동굴", "흩어진 물길" };
        string[] files = { "hallucination_anchorage.png", "madness_cave.png", "scattered_waterway.png" };

        for (int i = 0; i < names.Length; i++)
        {
            int index = i;
            var tile = new Panel
            {
                Dock = DockStyle.Fill,
                Margin = new Padding(5, 2, 5, 2),
                BackColor = CardBg2,
                Cursor = Cursors.Hand,
                Tag = index
            };
            tile.Paint += (_, e) =>
            {
                bool selected = tile.Tag is int idx && idx == _abyssDungeon.SelectedIndex;
                using var pen = new Pen(selected ? Accent : Border, selected ? 2f : 1f);
                var r = tile.ClientRectangle;
                r.Width = Math.Max(0, r.Width - 1);
                r.Height = Math.Max(0, r.Height - 1);
                if (r.Width > 0 && r.Height > 0) e.Graphics.DrawRectangle(pen, r);
            };

            var inner = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Padding = new Padding(5) };
            inner.RowStyles.Add(new RowStyle(SizeType.Percent, 68));
            inner.RowStyles.Add(new RowStyle(SizeType.Percent, 32));

            var picture = new PictureBox
            {
                Dock = DockStyle.Fill,
                SizeMode = PictureBoxSizeMode.Zoom,
                BackColor = Color.FromArgb(5, 20, 35),
                Cursor = Cursors.Hand
            };
            try
            {
                string path = Path.Combine(UpdateManager.FindPackageRoot(), "FishingAutomation", "abyss", "templates", files[i]);
                if (File.Exists(path))
                {
                    using var source = Image.FromFile(path);
                    picture.Image = new Bitmap(source);
                }
            }
            catch { }

            var label = new Label
            {
                Text = names[i],
                Dock = DockStyle.Fill,
                ForeColor = Color.White,
                Font = new Font("맑은 고딕", 9f, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleCenter,
                Cursor = Cursors.Hand
            };

            Action select = () =>
            {
                if (AnyRunning || _activeMode is not null) return;
                _mode.SelectedIndex = 2;
                _abyssDungeon.SelectedIndex = index;
                UpdateDashboard();
            };
            tile.Click += (_, _) => select();
            picture.Click += (_, _) => select();
            label.Click += (_, _) => select();

            inner.Controls.Add(picture, 0, 0);
            inner.Controls.Add(label, 0, 1);
            tile.Controls.Add(inner);
            _dungeonCards.Add(tile);
            row.Controls.Add(tile, i, 0);
        }

        outer.Controls.Add(row, 0, 1);
        card.Controls.Add(outer);
        return card;
    }

'''
marker = "    private Control BuildQuickSettingsCard()\n"
if marker not in s:
    raise RuntimeError("BuildQuickSettingsCard marker not found")
s = s.replace(marker, gallery_method + marker, 1)

# Show watchdog in the existing system-status card.
old_system = '''        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 7, Padding = new Padding(18) };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        for (int i = 1; i < 7; i++) layout.RowStyles.Add(new RowStyle(SizeType.Percent, 16.666f));
        layout.Controls.Add(SectionTitle("시스템 상태"), 0, 0);
        layout.Controls.Add(StatusRow("게임 창 인식", _sysGameValue), 0, 1);
        layout.Controls.Add(StatusRow("이미지 템플릿", _sysTemplateValue), 0, 2);
        layout.Controls.Add(StatusRow("OCR", _sysOcrValue), 0, 3);
        layout.Controls.Add(StatusRow("키보드 입력", _sysInputValue), 0, 4);
        layout.Controls.Add(StatusRow("텔레그램 연결", _sysTelegramValue), 0, 5);
        layout.Controls.Add(StatusRow("업데이트 서버", _sysUpdateValue), 0, 6);'''
new_system = '''        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 8, Padding = new Padding(14) };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        for (int i = 1; i < 8; i++) layout.RowStyles.Add(new RowStyle(SizeType.Percent, 14.285f));
        layout.Controls.Add(SectionTitle("시스템 상태"), 0, 0);
        layout.Controls.Add(StatusRow("게임 창 인식", _sysGameValue), 0, 1);
        layout.Controls.Add(StatusRow("이미지 템플릿", _sysTemplateValue), 0, 2);
        layout.Controls.Add(StatusRow("OCR", _sysOcrValue), 0, 3);
        layout.Controls.Add(StatusRow("키보드 입력", _sysInputValue), 0, 4);
        layout.Controls.Add(StatusRow("와치독", _sysWatchdogValue), 0, 5);
        layout.Controls.Add(StatusRow("텔레그램 연결", _sysTelegramValue), 0, 6);
        layout.Controls.Add(StatusRow("업데이트 서버", _sysUpdateValue), 0, 7);'''
if old_system not in s:
    raise RuntimeError("v46 system status block not found")
s = s.replace(old_system, new_system, 1)

# Refresh gallery selection and watchdog UI state.
s = s.replace(
    "        _dungeonPicker.Visible = abyss;\n",
    "        _dungeonPicker.Visible = abyss;\n"
    "        if (_dungeonGallery is not null) _dungeonGallery.Visible = abyss;\n"
    "        foreach (var card in _dungeonCards) card.Invalidate();\n",
    1,
)
s = s.replace(
    "        _sysInputValue.ForeColor = _fishingBot.InputReady ? Green : Color.Orange;\n",
    "        _sysInputValue.ForeColor = _fishingBot.InputReady ? Green : Color.Orange;\n"
    "        _sysWatchdogValue.Text = \"작동 중\";\n"
    "        _sysWatchdogValue.ForeColor = Green;\n",
    1,
)

write_text(p, s)

# Windows file/product version.
p = app / "FishingAutomation.csproj"
s = read_text(p)
for key, value in {
    "Version": "47.0.0",
    "AssemblyVersion": "47.0.0.0",
    "FileVersion": "47.0.0.0",
}.items():
    pattern = rf'<{key}>[^<]+</{key}>'
    replacement = f'<{key}>{value}</{key}>'
    if re.search(pattern, s):
        s = re.sub(pattern, replacement, s, count=1)
    else:
        s = s.replace("<PropertyGroup>", "<PropertyGroup>\n    " + replacement, 1)
write_text(p, s)

(root / "CHANGES_v47_V46_UI.txt").write_text(
    "Mabi_Auto v47 - v46 stable base UI refresh\n\n"
    "- Base: v46 gameplay/recognition/click flow unchanged\n"
    "- Window title: Mabi_Auto\n"
    "- Dashboard redesigned toward the approved dark Option 2 layout\n"
    "- Added three Abyss dungeon artwork selector cards using existing v46 templates\n"
    "- Existing potion shortage ESC close monitor preserved\n"
    "- Existing watchdog preserved and surfaced in system status\n"
    "- Existing automatic updater preserved\n",
    encoding="utf-8",
)

print("v47 applied on v46 stable base: UI/title only; popup close, watchdog and updater preserved")
