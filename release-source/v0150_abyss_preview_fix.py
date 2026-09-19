from pathlib import Path
import sys

root=Path(sys.argv[1]).resolve()
refui=root/'FishingAutomation'/'MainForm.ReferenceUI.cs'
text=refui.read_text(encoding='utf-8-sig')

replacements={
    'LoadDungeonPreview("hallucination_anchorage.jpg")':'LoadDungeonPreview("hallucination_anchorage.png")',
    'LoadDungeonPreview("madness_cave.jpg")':'LoadDungeonPreview("madness_cave.png")',
    'LoadDungeonPreview("scattered_waterway.jpg")':'LoadDungeonPreview("scattered_waterway.png")',
    'Path.Combine(AppContext.BaseDirectory, "abyss", "previews", fileName)':'Path.Combine(AppContext.BaseDirectory, "abyss", "templates", fileName)',
}
for old,new in replacements.items():
    if old not in text:
        raise SystemExit('missing expected preview anchor: '+old)
    text=text.replace(old,new,1)
refui.write_text(text,encoding='utf-8',newline='\n')

for name in ('hallucination_anchorage.png','madness_cave.png','scattered_waterway.png'):
    p=root/'FishingAutomation'/'abyss'/'templates'/name
    if not p.exists() or p.stat().st_size<=0:
        raise SystemExit('missing abyss preview source image: '+str(p))

for p in root.rglob('*'):
    if not p.is_file() or {'bin','obj','debug'} & set(p.relative_to(root).parts):
        continue
    if p.suffix.lower() not in {'.cs','.csproj','.json','.cmd','.ps1','.txt','.md'}:
        continue
    try:
        s=p.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        continue
    n=(s.replace('V0.1.49','V0.1.50')
         .replace('0.1.49.0','0.1.50.0')
         .replace('0.1.49','0.1.50'))
    if n!=s:
        p.write_text(n,encoding='utf-8',newline='\n')

check=refui.read_text(encoding='utf-8-sig')
for marker in (
    'LoadDungeonPreview("hallucination_anchorage.png")',
    'LoadDungeonPreview("madness_cave.png")',
    'LoadDungeonPreview("scattered_waterway.png")',
    'Path.Combine(AppContext.BaseDirectory, "abyss", "templates", fileName)',
):
    if marker not in check:
        raise SystemExit('preview fix marker missing: '+marker)
if '"abyss", "previews"' in check:
    raise SystemExit('obsolete abyss/previews lookup remains')
if 'hallucination_anchorage.jpg' in check or 'madness_cave.jpg' in check or 'scattered_waterway.jpg' in check:
    raise SystemExit('obsolete JPG preview filename remains')

proj=(root/'FishingAutomation'/'FishingAutomation.csproj').read_text(encoding='utf-8-sig')
upd=(root/'FishingAutomation'/'UpdateManager.cs').read_text(encoding='utf-8-sig')
if '<Version>0.1.50</Version>' not in proj:
    raise SystemExit('project version not bumped to 0.1.50')
if 'CurrentVersion = "V0.1.50"' not in upd:
    raise SystemExit('UpdateManager version not bumped to V0.1.50')

print('V0.1.50 abyss preview path/extension fix applied')
