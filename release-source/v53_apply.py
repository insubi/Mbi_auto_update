#!/usr/bin/env python3
from pathlib import Path
import re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(p): return p.read_text(encoding="utf-8-sig")
def write(p, s): p.write_text(s, encoding="utf-8-sig")
def swap(s, old, new, label):
    if old not in s:
        raise RuntimeError(f"v53 pattern missing: {label}")
    return s.replace(old, new, 1)

# Version bump.
p = app / "UpdateManager.cs"
s = read(p)
s = swap(s, 'public const string CurrentVersion = "v52";', 'public const string CurrentVersion = "v53";', 'UpdateManager version')
write(p, s)

p = app / "MainForm.Dashboard.cs"
s = read(p)
s = swap(s, 'Text = "v52.0.0"', 'Text = "v53.0.0"', 'dashboard version')
write(p, s)

p = app / "FishingAutomation.csproj"
s = read(p)
for k, v in {"Version":"53.0.0", "AssemblyVersion":"53.0.0.0", "FileVersion":"53.0.0.0"}.items():
    pat = rf'<{k}>[^<]+</{k}>'
    if not re.search(pat, s):
        raise RuntimeError(f"v53 project version tag missing: {k}")
    s = re.sub(pat, f'<{k}>{v}</{k}>', s, count=1)
write(p, s)

# Keep the legacy selector and ReferenceUI bottom picker in sync with mode changes.
p = app / "MainForm.cs"
s = read(p)
old = '''    private void UpdateAbyssSelectorVisibility()\n    {\n        bool show = SelectedMode == "어비스";\n        _abyssDungeonLabel.Visible = show;\n        _abyssDungeon.Visible = show;\n        _abyssDungeon.Enabled = show && _activeMode is null;\n    }'''
new = '''    private void UpdateAbyssSelectorVisibility()\n    {\n        bool show = SelectedMode == "어비스";\n        _abyssDungeonLabel.Visible = show;\n        _abyssDungeon.Visible = show;\n        _abyssDungeon.Enabled = show && _activeMode is null;\n        _referenceDashboard?.UpdateAbyssDungeonPickerVisibility();\n    }'''
s = swap(s, old, new, 'mode selector visibility hook')
write(p, s)

# ReferenceUI: bottom Abyss dungeon cards/buttons exist only while Abyss is selected/active.
p = app / "MainForm.ReferenceUI.cs"
s = read(p)

s = swap(s,
'''        private float ScaleX => Math.Max(1, Width) / 1448f;\n        private float ScaleY => Math.Max(1, Height) / 1086f;''',
'''        private float ScaleX => Math.Max(1, Width) / 1448f;\n        private float ScaleY => Math.Max(1, Height) / 1086f;\n        private bool ShouldShowAbyssDungeonPicker =>\n            string.Equals(_owner._activeMode ?? _owner._mode.SelectedItem?.ToString(), "어비스", StringComparison.Ordinal);''',
'show Abyss picker condition')

s = swap(s,
'''            _positions.Add((owner._logView, new(220, 634, 1210, 305)));\n            AccessibleName = "Mabi Auto 대시보드";\n        }''',
'''            _positions.Add((owner._logView, new(220, 634, 1210, 305)));\n            UpdateAbyssDungeonPickerVisibility();\n            AccessibleName = "Mabi Auto 대시보드";\n        }''',
'initial picker visibility')

s = swap(s,
'''        public void SetLogExpanded(bool expanded)\n        {\n            _owner._logView.Visible = expanded;\n            foreach (var button in _gallery) button.Visible = !expanded;\n            if (expanded) _owner._logView.BringToFront();\n            Invalidate();\n        }''',
'''        public void UpdateAbyssDungeonPickerVisibility()\n        {\n            bool showButtons = ShouldShowAbyssDungeonPicker && !_owner._logExpanded;\n            foreach (var button in _gallery) button.Visible = showButtons;\n            Invalidate();\n        }\n\n        public void SetLogExpanded(bool expanded)\n        {\n            _owner._logView.Visible = expanded;\n            UpdateAbyssDungeonPickerVisibility();\n            if (expanded) _owner._logView.BringToFront();\n            Invalidate();\n        }''',
'picker button visibility')

s = swap(s,
'''            if (!_owner._logExpanded && y >= 685 && y <= 921 && x >= 235 && x < 1415)\n                SelectDungeon(Math.Clamp((int)((x - 235) / 392), 0, 2));''',
'''            if (ShouldShowAbyssDungeonPicker && !_owner._logExpanded && y >= 685 && y <= 921 && x >= 235 && x < 1415)\n                SelectDungeon(Math.Clamp((int)((x - 235) / 392), 0, 2));''',
'picker mouse hit area')

old_paint = '''            Card(g, new(219, 634, 1212, 305));\n            Icon(g, "game", new(240, 650, 29, 26), _text);\n            TextAt(g, "어비스 던전 선택", new(286, 644, 1089, 37), 21, true, Color.White);\n            string[] names = { "허상의 정박지", "광기의 동굴", "흩어진 물길" };\n            string[] desc = { "고요 속에 가라앉은 진실", "뒤틀린 광기의 울림", "흩어진 흐름이 이어지는 곳" };\n            Rectangle[] source = { new(242, 693, 366, 103), new(636, 693, 365, 103), new(1027, 693, 382, 103) };\n            for (int i = 0; i < 3; i++)\n            {\n                int x = 235 + i * 392;\n                int tileWidth = i == 2 ? 396 : 380;\n                Card(g, new(x, 685, tileWidth, 236), i == _owner._abyssDungeon.SelectedIndex);\n                Artwork(g, new(x + 6, 692, tileWidth - 12, 105), source[i]);\n                TextAt(g, names[i], new(x + 12, 801, tileWidth - 24, 33), 20, true, Color.White, StringAlignment.Center);\n                TextAt(g, desc[i], new(x + 12, 833, tileWidth - 24, 28), 17, false, _text, StringAlignment.Center);\n            }'''
new_paint = '''            if (ShouldShowAbyssDungeonPicker)\n            {\n                Card(g, new(219, 634, 1212, 305));\n                Icon(g, "game", new(240, 650, 29, 26), _text);\n                TextAt(g, "어비스 던전 선택", new(286, 644, 1089, 37), 21, true, Color.White);\n                string[] names = { "허상의 정박지", "광기의 동굴", "흩어진 물길" };\n                string[] desc = { "고요 속에 가라앉은 진실", "뒤틀린 광기의 울림", "흩어진 흐름이 이어지는 곳" };\n                Rectangle[] source = { new(242, 693, 366, 103), new(636, 693, 365, 103), new(1027, 693, 382, 103) };\n                for (int i = 0; i < 3; i++)\n                {\n                    int x = 235 + i * 392;\n                    int tileWidth = i == 2 ? 396 : 380;\n                    Card(g, new(x, 685, tileWidth, 236), i == _owner._abyssDungeon.SelectedIndex);\n                    Artwork(g, new(x + 6, 692, tileWidth - 12, 105), source[i]);\n                    TextAt(g, names[i], new(x + 12, 801, tileWidth - 24, 33), 20, true, Color.White, StringAlignment.Center);\n                    TextAt(g, desc[i], new(x + 12, 833, tileWidth - 24, 28), 17, false, _text, StringAlignment.Center);\n                }\n            }'''
s = swap(s, old_paint, new_paint, 'bottom Abyss picker painting')
s = swap(s, 'TextAt(g, "v52.0.0 · UI"', 'TextAt(g, "v53.0.0 · UI"', 'ReferenceUI version')
write(p, s)

(root / "CHANGES_v53_ABYSS_PICKER_VISIBILITY.txt").write_text(
    "Mabi_Auto v53\n"
    "- Bottom Abyss dungeon picker is shown only when Abyss is selected or actively running.\n"
    "- Fishing and Dungeon modes hide all three Abyss cards and their Select buttons.\n"
    "- Hidden Abyss card area no longer reacts to mouse clicks.\n"
    "- Selecting Abyss from Current Mode or the left navigation immediately shows the picker.\n",
    encoding="utf-8",
)
print("v53 Abyss picker visibility patch applied")
