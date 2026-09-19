from pathlib import Path
import sys,zipfile
root=Path(sys.argv[1])
for p in root.rglob('*'):
    if p.is_file() and p.suffix in {'.cs','.csproj'} and not {'bin','obj'} & set(p.relative_to(root).parts):
        old=p.read_text(encoding='utf-8-sig')
        new=old.replace('V0.1.48','V0.1.49').replace('0.1.48.0','0.1.49.0').replace('<Version>0.1.48</Version>','<Version>0.1.49</Version>')
        if old!=new: p.write_text(new,encoding='utf-8',newline='\n')
assert '<Version>0.1.49</Version>' in (root/'FishingAutomation/FishingAutomation.csproj').read_text(encoding='utf-8-sig')
assert 'CurrentVersion = "V0.1.49"' in (root/'FishingAutomation/UpdateManager.cs').read_text(encoding='utf-8-sig')
Path('out').mkdir(exist_ok=True)
with zipfile.ZipFile('out/MabiAuto_V0.1.49_Source.zip','w',zipfile.ZIP_DEFLATED) as z:
    for folder in ['FishingAutomation','MacroWatchdog','tools']:
        for p in (root/folder).rglob('*'):
            if p.is_file() and not {'bin','obj','debug'} & set(p.relative_to(root).parts):
                z.write(p,str(p.relative_to(root)))
    z.write('release-source/v0149_release_notes.md','RELEASE_NOTES.md')
print('V0.1.49 app metadata and source package ready')
