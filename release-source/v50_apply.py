#!/usr/bin/env python3
from pathlib import Path
import re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(p): return p.read_text(encoding="utf-8-sig")
def write(p, s): p.write_text(s, encoding="utf-8-sig")
def swap(s, a, b):
    if a not in s: raise RuntimeError("UI base pattern not found")
    return s.replace(a, b, 1)

u = app / "UpdateManager.cs"
s = read(u)
s = swap(s, 'public const string CurrentVersion = "v49";', 'public const string CurrentVersion = "v50";')
write(u, s)

p = app / "MainForm.Dashboard.cs"
s = read(p)
s = swap(s, 'root.RowStyles.Add(new RowStyle(SizeType.Absolute, 88));', 'root.RowStyles.Add(new RowStyle(SizeType.Absolute, 68));')
s = swap(s, 'Text = "v49.0.0"', 'Text = "v50.0.0"')
s = swap(s,
'        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 5, RowCount = 1, Margin = Padding.Empty };\n        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 280));\n        for (int i = 1; i < 5; i++) layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));',
'        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, Margin = Padding.Empty };\n        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 300));\n        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));')
s = swap(s,
'        layout.Controls.Add(StatusChip(_topGameChip, "게임 감지"), 1, 0);\n        layout.Controls.Add(StatusChip(_topOcrChip, "OCR 준비"), 2, 0);\n        layout.Controls.Add(StatusChip(_topTemplateChip, "템플릿 매칭"), 3, 0);\n        layout.Controls.Add(StatusChip(_topInputChip, "키보드 입력"), 4, 0);',
'        layout.Controls.Add(new Label { Text = "●  시스템 상태", Dock = DockStyle.Fill, ForeColor = Green, Font = new Font("맑은 고딕", 9f, FontStyle.Bold), TextAlign = ContentAlignment.MiddleRight }, 1, 0);')
s = swap(s,
'        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 64));\n        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 36));',
'        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));\n        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 0));')
s = swap(s, 'var card = BorderedPanel(Color.FromArgb(9, 34, 62));', 'var card = BorderedPanel(Color.FromArgb(6, 36, 70));')
s = s.replace('SizeMode = PictureBoxSizeMode.StretchImage', 'SizeMode = PictureBoxSizeMode.Zoom')
s = s.replace('using var pen = new Pen(selected ? Accent : Line, selected ? 3f : 1f);', 'using var pen = new Pen(selected ? Color.FromArgb(0, 190, 255) : Line, selected ? 4f : 1f);', 1)
write(p, s)

proj = app / "FishingAutomation.csproj"
s = read(proj)
for k, v in {"Version":"50.0.0", "AssemblyVersion":"50.0.0.0", "FileVersion":"50.0.0.0"}.items():
    pat = rf'<{k}>[^<]+</{k}>'; rep = f'<{k}>{v}</{k}>'
    s = re.sub(pat, rep, s, count=1) if re.search(pat, s) else s.replace("<PropertyGroup>", "<PropertyGroup>\n    "+rep, 1)
write(proj, s)
print("v50 UI refresh applied")
