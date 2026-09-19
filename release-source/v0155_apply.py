from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1]).resolve()
app = root / 'FishingAutomation'
engine = app / 'dungeon/ScenarioEngine.cs'
retry = app / 'dungeon/ScenarioEngine.AbyssRetry.cs'
expected_retry = 'e7de708a7e3483ca753f41a950251ab9f0f616d25f1a2645225ee0057e415ca3'
if hashlib.sha256(retry.read_bytes()).hexdigest() != expected_retry:
    raise SystemExit('V0.1.54 retry source hash mismatch')
def read(p): return p.read_text(encoding='utf-8-sig')
def write(p, s): p.write_text(s, encoding='utf-8', newline='\n')
update = app / 'UpdateManager.cs'
project = app / 'FishingAutomation.csproj'
if 'CurrentVersion = "V0.1.54"' not in read(update):
    raise SystemExit('Expected V0.1.54 base')
s = read(engine)
anchor = '''    private async Task<DetectionResult> DetectAbyssConfirmedClearAsync(Bitmap frame, CancellationToken ct)
    {
'''
if s.count(anchor) != 1: raise SystemExit('Clear detector anchor mismatch')
s = s.replace(anchor, anchor + '''        if (IsAbyss)
            return await DetectAbyssClearPromptAsync(frame, ct);
''', 1)
write(engine, s)
overlay = Path(__file__).parent / 'v0155-overlay/FishingAutomation/dungeon/ScenarioEngine.AbyssRetry.cs'
write(retry, read(overlay))
write(update, read(update).replace('CurrentVersion = "V0.1.54"', 'CurrentVersion = "V0.1.55"', 1))
write(project, read(project).replace('0.1.54', '0.1.55'))
print('V0.1.55 applied: recognize clear before results; recover clear animation in result wait')
