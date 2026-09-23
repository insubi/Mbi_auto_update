from pathlib import Path
import hashlib, json, re, shutil, sys
root = Path(sys.argv[1]).resolve()
overlay = Path(__file__).resolve().parent / 'v0171-overlay'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(): return {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*') if p.is_file()}
before = snapshot()
engine = root/'FishingAutomation/dungeon/ScenarioEngine.cs'
original_engine = engine.read_text(encoding='utf-8-sig')
allowed = set()
for p in overlay.rglob('*'):
    if p.is_file():
        rel = p.relative_to(overlay)
        target = root/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
        allowed.add(rel.as_posix())
for rel, replacements in {
    'FishingAutomation/FishingAutomation.csproj': [('0.1.70','0.1.71')],
    'FishingAutomation/UpdateManager.cs': [('CurrentVersion = "V0.1.70"','CurrentVersion = "V0.1.71"')],
}.items():
    p=root/rel
    text=p.read_text(encoding='utf-8-sig')
    for old,new in replacements:
        assert old in text, f'Missing version marker: {rel}'
        text=text.replace(old,new)
    p.write_text(text,encoding='utf-8')
    allowed.add(rel)
after = snapshot()
changed = {k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
assert changed <= allowed, f'Unexpected changes: {changed-allowed}'
patched_engine = engine.read_text(encoding='utf-8-sig')
for start,end in [
    ('    private async Task<DetectionResult> WaitForAbyssTouchPromptAsync','    private async Task AdvanceAbyssClearScreenAsync'),
    ('    private async Task AdvanceAbyssClearScreenAsync','    private async Task WaitForAbyssHomeAfterNormalExitAsync'),
]:
    assert original_engine[original_engine.index(start):original_engine.index(end)] == patched_engine[patched_engine.index(start):patched_engine.index(end)], start
assert 'if (clearTitle.Found && touch.Found)' in patched_engine
for p in (root/'FishingAutomation').rglob('*'):
    if p.suffix in ('.cs','.json'):
        assert not re.search(r'abyss_death|AbyssDeath|DeathTimeout|사망',p.read_text(encoding='utf-8-sig')), p
scenario=json.loads((root/'FishingAutomation/abyss/config/scenario.json').read_text(encoding='utf-8-sig'))
combat=next(s for s in scenario['Steps'] if s['Target']=='abyss_touch_screen')
assert combat['TimeoutSeconds']==600
print('PASS V0.1.71: only approved files changed; normal touch/result/retry/loot preserved; death logic removed')
