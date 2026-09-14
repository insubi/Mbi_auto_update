#!/usr/bin/env python3
from pathlib import Path
import re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(p): return p.read_text(encoding="utf-8-sig")
def write(p, s): p.write_text(s, encoding="utf-8-sig")
def swap(s, a, b):
    if a not in s:
        raise RuntimeError(f"required v50 UI pattern missing: {a[:100]}")
    return s.replace(a, b, 1)

# v51 is UI-only. Keep all v50 automation/runtime behavior unchanged.
u = app / "UpdateManager.cs"
s = read(u)
s = swap(s, 'public const string CurrentVersion = "v50";', 'public const string CurrentVersion = "v51";')
write(u, s)

p = app / "MainForm.Dashboard.cs"
s = read(p)

# v50 reduced the header row from 88px to 68px. On DPI-scaled Windows this
# clips almost the entire brand/status line. Restore the known-good room and
# reduce vertical padding slightly so the header remains fully visible.
s = swap(s,
    'root.RowStyles.Add(new RowStyle(SizeType.Absolute, 68));',
    'root.RowStyles.Add(new RowStyle(SizeType.Absolute, 92));')
s = swap(s,
    'var header = new Panel { Dock = DockStyle.Fill, BackColor = NavBg, Padding = new Padding(22, 8, 18, 8) };',
    'var header = new Panel { Dock = DockStyle.Fill, BackColor = NavBg, Padding = new Padding(22, 4, 18, 4) };')
s = swap(s, 'Text = "v50.0.0"', 'Text = "v51.0.0"')
write(p, s)

proj = app / "FishingAutomation.csproj"
s = read(proj)
for k, v in {"Version":"51.0.0", "AssemblyVersion":"51.0.0.0", "FileVersion":"51.0.0.0"}.items():
    pat = rf'<{k}>[^<]+</{k}>'
    rep = f'<{k}>{v}</{k}>'
    if re.search(pat, s):
        s = re.sub(pat, rep, s, count=1)
    else:
        s = s.replace("<PropertyGroup>", "<PropertyGroup>\n    " + rep, 1)
write(proj, s)

(root / "CHANGES_v51_HEADER_FIX.txt").write_text(
    "Mabi_Auto v51 UI-only fix\n"
    "- Restore full top header height on DPI-scaled Windows\n"
    "- Reduce header vertical padding to prevent brand/status clipping\n"
    "- No gameplay, Abyss, popup, watchdog, updater, OCR, input, or detector changes\n",
    encoding="utf-8"
)

print("v51 header clipping fix applied; runtime logic unchanged")
