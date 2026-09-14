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
s = swap(s, 'var card = BorderedPanel(Color.FromArgb(9, 34, 62));', '''var card = BorderedPanel(Color.FromArgb(6, 36, 70));
        card.Paint += (_, e) =>
        {
            var r = card.ClientRectangle;
            if (r.Width < 2 || r.Height < 2) return;
            using var bg = new System.Drawing.Drawing2D.LinearGradientBrush(r, Color.FromArgb(5, 24, 52), Color.FromArgb(12, 74, 132), 0f);
            e.Graphics.FillRectangle(bg, r);
            e.Graphics.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.AntiAlias;
            using var pen = new Pen(Color.FromArgb(100, 71, 176, 255), 2f);
            using var dark = new SolidBrush(Color.FromArgb(150, 2, 17, 35));
            int ground = r.Height - 15;
            int start = Math.Max(430, r.Width / 3);
            for (int i = 0; i < 7; i++)
            {
                int x = start + i * 85;
                int h = 38 + (i % 3) * 12;
                e.Graphics.FillRectangle(dark, x, ground - h, 20, h);
            }
            for (int i = 0; i < 4; i++)
            {
                int x = start + 35 + i * 135;
                e.Graphics.DrawArc(pen, x, ground - 60, 62, 60, 180, 180);
                e.Graphics.DrawLine(pen, x, ground - 30, x, ground);
                e.Graphics.DrawLine(pen, x + 62, ground - 30, x + 62, ground);
            }
            using var moon = new SolidBrush(Color.FromArgb(205, 204, 230, 255));
            e.Graphics.FillEllipse(moon, r.Width - 145, 18, 42, 42);
            e.Graphics.DrawLine(pen, start - 20, ground, r.Width - 20, ground);
        };''')
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
