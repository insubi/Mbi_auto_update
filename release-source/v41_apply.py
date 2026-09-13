#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

p = app / "UpdateManager.cs"
s = p.read_text(encoding="utf-8-sig")
if 'public const string CurrentVersion = "v40";' not in s:
    raise RuntimeError("v40 base not found")
p.write_text(s.replace('public const string CurrentVersion = "v40";', 'public const string CurrentVersion = "v41";', 1), encoding="utf-8-sig")

p = app / "abyss" / "config" / "targets.json"
data = json.loads(p.read_text(encoding="utf-8-sig"))
t = next((x for x in data if x.get("Id") == "abyss_touch_screen"), None)
if t is None or not t.get("TemplatePath"):
    raise RuntimeError("abyss_touch_screen target invalid")
t.update({
    "Kind": "hybrid",
    "Threshold": 0.68,
    "TemplateScaleMin": 0.60,
    "TemplateScaleMax": 1.55,
    "TemplateScaleStep": 0.05,
    "Text": "화면을 터치해 주세요",
    "MaxEditDistance": 3,
    "OcrRetryAt2x": True
})
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

p = app / "MainForm.cs"
s = p.read_text(encoding="utf-8-sig")
s = re.sub(r'Text\s*=\s*"MABI AUTO[^\"]*";', 'Text = "MABI AUTO · v41";', s, count=1)
p.write_text(s, encoding="utf-8-sig")

p = app / "FishingAutomation.csproj"
s = p.read_text(encoding="utf-8-sig")
for k,v in {"Version":"41.0.0","AssemblyVersion":"41.0.0.0","FileVersion":"41.0.0.0"}.items():
    s = re.sub(rf'<{k}>[^<]+</{k}>', f'<{k}>{v}</{k}>', s, count=1)
p.write_text(s, encoding="utf-8-sig")

print("v41 touch-screen recognition patch applied")
