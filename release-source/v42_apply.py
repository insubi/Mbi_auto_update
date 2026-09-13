#!/usr/bin/env python3
from pathlib import Path
import base64, json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def repl(path, old, new):
    s = path.read_text(encoding="utf-8-sig")
    if old not in s:
        raise RuntimeError(f"pattern not found in {path}: {old[:80]}")
    path.write_text(s.replace(old, new, 1), encoding="utf-8-sig")

repl(app / "UpdateManager.cs",
     'public const string CurrentVersion = "v41";',
     'public const string CurrentVersion = "v42";')

p = app / "MainForm.cs"
s = p.read_text(encoding="utf-8-sig")
changes = {
    'Text = "MABI AUTO · v41";':'Text = "MABI AUTO · v42";',
    'Width = 1320;':'Width = 1100;',
    'Height = 840;':'Height = 720;',
    'MinimumSize = new Size(1120, 720);':'MinimumSize = new Size(1020, 680);',
    'Font = new Font("맑은 고딕", 9f);':'Font = new Font("맑은 고딕", 8.5f);',
    'Font = new Font("Segoe UI", 11.5f, FontStyle.Bold)':'Font = new Font("Segoe UI", 9.5f, FontStyle.Bold)'
}
for old,new in changes.items():
    if old not in s:
        raise RuntimeError(f"MainForm pattern not found: {old}")
    s=s.replace(old,new,1)
p.write_text(s, encoding="utf-8-sig")

p = app / "MainForm.Dashboard.cs"
s = p.read_text(encoding="utf-8-sig")
replacements = [
('Height = 38,\n            Width = 135,','Height = 32,\n            Width = 120,'),
('Margin = new Padding(4),','Margin = new Padding(2),'),
('Font = new Font("맑은 고딕", 9f, FontStyle.Bold)','Font = new Font("맑은 고딕", 8f, FontStyle.Bold)'),
('Height = 58,','Height = 44,'),
('Padding = new Padding(18, 0, 0, 0),','Padding = new Padding(12, 0, 0, 0),'),
('Font = new Font("맑은 고딕", 10.5f, selected ? FontStyle.Bold : FontStyle.Regular)','Font = new Font("맑은 고딕", 8.5f, selected ? FontStyle.Bold : FontStyle.Regular)'),
('private Label TextLabel(string text, float size = 10)','private Label TextLabel(string text, float size = 8.5f)'),
('Height = 48,\n        ForeColor = TitleText,\n        Font = new Font("맑은 고딕", 12f, FontStyle.Bold),','Height = 32,\n        ForeColor = TitleText,\n        Font = new Font("맑은 고딕", 10f, FontStyle.Bold),'),
('root.RowStyles.Add(new RowStyle(SizeType.Absolute, 78));','root.RowStyles.Add(new RowStyle(SizeType.Absolute, 60));'),
('root.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));','root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));'),
('Padding = new Padding(24, 8, 18, 8)','Padding = new Padding(16, 6, 12, 6)'),
('Width = 250,\n            ForeColor = Color.White,\n            Font = new Font("Segoe UI", 20f, FontStyle.Bold),','Width = 190,\n            ForeColor = Color.White,\n            Font = new Font("Segoe UI", 16f, FontStyle.Bold),'),
('Text = "마비노기 모바일 매크로  ·  Dashboard v40",','Text = "마비노기 모바일 매크로  ·  Dashboard v42",'),
('Width = 420,','Width = 340,'),
('Font = new Font("맑은 고딕", 9.5f),','Font = new Font("맑은 고딕", 8f),'),
('_readyBadge.Width = 170;','_readyBadge.Width = 145;'),
('_readyBadge.Font = new Font("맑은 고딕", 9.5f, FontStyle.Bold);','_readyBadge.Font = new Font("맑은 고딕", 8.5f, FontStyle.Bold);'),
('body.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 205));','body.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 170));'),
('Padding = new Padding(10, 18, 10, 12)','Padding = new Padding(8, 12, 8, 8)'),
('Height = 360,','Height = 276,'),
('menu.RowStyles.Add(new RowStyle(SizeType.Absolute, 58))','menu.RowStyles.Add(new RowStyle(SizeType.Absolute, 44))'),
('Height = 115,','Height = 82,'),
('Font = new Font("맑은 고딕", 9f),','Font = new Font("맑은 고딕", 8f),'),
('Padding = new Padding(14),','Padding = new Padding(8),'),
('var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5, Padding = new Padding(18) };','var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 5, Padding = new Padding(10) };'),
('layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));\n        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 52));\n        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 74));\n        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));\n        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));',
 'layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 32));\n        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));\n        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));\n        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 96));\n        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));'),
('_currentDungeonValue.Font = new Font("맑은 고딕", 15f, FontStyle.Bold);','_currentDungeonValue.Font = new Font("맑은 고딕", 12f, FontStyle.Bold);'),
('Text = "v40  |  Mabi Auto"','Text = "v42  |  Mabi Auto"'),
('MinimumSize = new Size(420, 230);','MinimumSize = new Size(360, 210);'),
('Size = new Size(560, 280);','Size = new Size(480, 240);'),
('MinimumSize = new Size(1120, 720);','MinimumSize = new Size(1020, 680);')
]
for old,new in replacements:
    if old in s:
        s=s.replace(old,new,1)

old_block = '''        _dashboard.Controls.Add(BuildRunStateCard(), 0, 0);
        _dashboard.Controls.Add(BuildCurrentDungeonCard(), 1, 0);
        _dashboard.Controls.Add(BuildQuickSettingsCard(), 2, 0);
        _logView = BuildLogPanel();
        _dashboard.Controls.Add(_logView, 0, 1);
        _dashboard.Controls.Add(BuildStatsCard(), 1, 1);
        _dashboard.Controls.Add(BuildSystemStatusCard(), 2, 1);'''
new_block = '''        _dashboard.Controls.Add(BuildRunStateCard(), 0, 0);
        _dashboard.Controls.Add(BuildCurrentDungeonCard(), 1, 0);
        _dashboard.Controls.Add(BuildQuickSettingsCard(), 2, 0);
        var stats = BuildStatsCard();
        _dashboard.Controls.Add(stats, 0, 1);
        _dashboard.SetColumnSpan(stats, 2);
        _dashboard.Controls.Add(BuildSystemStatusCard(), 2, 1);'''
if old_block not in s:
    raise RuntimeError("dashboard log block not found")
s=s.replace(old_block,new_block,1)

for old,new in [
('new Font("맑은 고딕", 20f, FontStyle.Bold)','new Font("맑은 고딕", 16f, FontStyle.Bold)'),
('new Font("맑은 고딕", 9f)','new Font("맑은 고딕", 8f)'),
('new Font("맑은 고딕", 8.8f, FontStyle.Bold)','new Font("맑은 고딕", 8f, FontStyle.Bold)'),
('new Font("맑은 고딕", 9.5f)','new Font("맑은 고딕", 8.3f)'),
('new Font("맑은 고딕", 10f, FontStyle.Bold)','new Font("맑은 고딕", 8.5f, FontStyle.Bold)'),
('new Font("맑은 고딕", 8.5f)','new Font("맑은 고딕", 7.5f)'),
('new Font("Segoe UI", 8.5f)','new Font("Segoe UI", 7.5f)')
]:
    s=s.replace(old,new)
p.write_text(s, encoding="utf-8-sig")

tpl = app / "abyss" / "templates" / "popup_close.png"
tpl.write_bytes(base64.b64decode("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"))

p = app / "abyss" / "config" / "targets.json"
targets = json.loads(p.read_text(encoding="utf-8-sig"))
targets = [t for t in targets if t.get("Id") != "abyss_popup_close"]
targets.append({
    "Id":"abyss_popup_close",
    "Kind":"hybrid",
    "Roi":{"X":140,"Y":800,"Width":300,"Height":190},
    "Text":"닫기",
    "TemplatePath":"templates/popup_close.png",
    "Threshold":0.72,
    "TemplateScaleMin":0.70,
    "TemplateScaleMax":1.40,
    "TemplateScaleStep":0.05,
    "MaxEditDistance":1,
    "OcrRetryAt2x":True
})
p.write_text(json.dumps(targets, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

p = app / "abyss" / "config" / "scenario.json"
scenario = json.loads(p.read_text(encoding="utf-8-sig"))
mons = [m for m in scenario.get("Monitors", []) if m.get("Target") != "abyss_popup_close"]
mons.insert(0, {
    "Target":"abyss_popup_close",
    "Action":"click",
    "CooldownMs":1500,
    "ScanIntervalMs":700
})
scenario["Monitors"] = mons
p.write_text(json.dumps(scenario, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

p = app / "FishingAutomation.csproj"
s = p.read_text(encoding="utf-8-sig")
for k,v in {"Version":"42.0.0","AssemblyVersion":"42.0.0.0","FileVersion":"42.0.0.0"}.items():
    s = re.sub(rf'<{k}>[^<]+</{k}>', f'<{k}>{v}</{k}>', s, count=1)
p.write_text(s, encoding="utf-8-sig")

print("v42 compact UI + popup close patch applied")
