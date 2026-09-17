#!/usr/bin/env python3
from pathlib import Path
import json, re, sys, hashlib

if len(sys.argv) != 2:
    raise SystemExit('usage: v0128_full_stability_audit.py SOURCE_ROOT')

root = Path(sys.argv[1]).resolve()
app = root / 'FishingAutomation'
findings = []
checks = []

def finding(sev, area, msg):
    findings.append((sev, area, msg))

def ok(area, msg):
    checks.append((area, msg))

def read(p):
    return p.read_text(encoding='utf-8-sig')

def load_json(p):
    try:
        return json.loads(read(p))
    except Exception as e:
        finding('HIGH', str(p.relative_to(root)), f'JSON parse failed: {e}')
        return None

def sha256(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

if not app.exists():
    raise SystemExit(f'FishingAutomation missing: {app}')

# --- Build/config surface ---
csproj = app / 'FishingAutomation.csproj'
if not csproj.exists():
    finding('HIGH','build','FishingAutomation.csproj missing')
else:
    ok('build','FishingAutomation.csproj present')

# Validate scenarios/targets for every mode.
for mode in ['dungeon','abyss']:
    base = app / mode
    scenario_p = base / 'config' / 'scenario.json'
    targets_p = base / 'config' / 'targets.json'
    if not scenario_p.exists() or not targets_p.exists():
        finding('HIGH', mode, 'scenario.json or targets.json missing')
        continue
    scenario = load_json(scenario_p)
    targets = load_json(targets_p)
    if scenario is None or targets is None:
        continue
    if not isinstance(targets, list):
        finding('HIGH', mode, 'targets.json is not a list')
        continue
    ids=[]
    for t in targets:
        tid=str(t.get('Id',''))
        if not tid:
            finding('HIGH',mode,'target without Id')
            continue
        ids.append(tid)
    dups=sorted({x for x in ids if ids.count(x)>1})
    if dups:
        finding('HIGH',mode,f'duplicate target Ids: {dups}')
    target_by_id={str(t.get('Id')):t for t in targets if t.get('Id')}

    for tid,t in target_by_id.items():
        kind=str(t.get('Kind','')).lower()
        if kind not in {'ocr','template','hybrid'}:
            finding('MEDIUM',mode,f'{tid}: unknown Kind={kind!r}')
        roi=t.get('Roi') or {}
        try:
            x,y,w,h=[int(roi[k]) for k in ('X','Y','Width','Height')]
            if w<=0 or h<=0:
                finding('HIGH',mode,f'{tid}: non-positive ROI {roi}')
            if x<0 or y<0 or x+w>800 or y+h>1000:
                finding('MEDIUM',mode,f'{tid}: ROI outside fixed 800x1000 client: {roi}')
        except Exception:
            finding('HIGH',mode,f'{tid}: invalid/missing ROI {roi}')
        if kind in {'ocr','hybrid'} and not str(t.get('Text','')).strip() and kind=='ocr':
            finding('HIGH',mode,f'{tid}: OCR target has empty Text')
        if kind in {'template','hybrid'} and t.get('TemplatePath'):
            tp=base / str(t['TemplatePath']).replace('/', str(Path('/')))
            # Path('/')->'/' on Windows/Python too; normalize explicitly if needed.
            tp=base / Path(str(t['TemplatePath']).replace('\\','/'))
            if not tp.exists():
                finding('HIGH',mode,f'{tid}: template missing: {t["TemplatePath"]}')
        if 'Threshold' in t:
            try:
                th=float(t['Threshold'])
                if not (0.0 < th <= 1.0):
                    finding('HIGH',mode,f'{tid}: invalid threshold {th}')
            except Exception:
                finding('HIGH',mode,f'{tid}: non-numeric threshold')
        if any(k in t for k in ('TemplateScaleMin','TemplateScaleMax','TemplateScaleStep')):
            try:
                mn=float(t.get('TemplateScaleMin',1)); mx=float(t.get('TemplateScaleMax',1)); st=float(t.get('TemplateScaleStep',0.1))
                if mn<=0 or mx<=0 or st<=0 or mn>mx:
                    finding('HIGH',mode,f'{tid}: invalid scale range {mn}..{mx} step {st}')
            except Exception:
                finding('HIGH',mode,f'{tid}: invalid scale values')

    steps=(scenario or {}).get('Steps') or []
    if not steps:
        finding('HIGH',mode,'scenario has no Steps')
    for i,s in enumerate(steps,1):
        target=str(s.get('Target',''))
        alt=str(s.get('AlternativeTarget','')) if s.get('AlternativeTarget') else ''
        if target and target not in target_by_id:
            finding('HIGH',mode,f'step {i} references missing target {target}')
        if alt and alt not in target_by_id:
            finding('HIGH',mode,f'step {i} references missing alternative {alt}')
        try:
            timeout=int(s.get('TimeoutSeconds',0))
            if timeout<=0:
                finding('MEDIUM',mode,f'step {i} has non-positive timeout {timeout}')
        except Exception:
            finding('MEDIUM',mode,f'step {i} timeout invalid')
    monitors=(scenario or {}).get('Monitors') or []
    for m in monitors:
        tid=str(m.get('Target',''))
        if tid not in target_by_id:
            finding('HIGH',mode,f'monitor references missing target {tid}')
        try:
            if int(m.get('ScanIntervalMs',0))<=0 or int(m.get('CooldownMs',0))<0:
                finding('MEDIUM',mode,f'monitor {tid} invalid timing')
        except Exception:
            finding('MEDIUM',mode,f'monitor {tid} timing not numeric')
    ok(mode,f'config refs validated: {len(steps)} steps, {len(monitors)} monitors, {len(target_by_id)} targets')

# --- Dungeon-specific behavior checks ---
d_targets = load_json(app/'dungeon/config/targets.json') or []
d_scenario = load_json(app/'dungeon/config/scenario.json') or {}
dby={t.get('Id'):t for t in d_targets if isinstance(t,dict)}
mons=[m for m in d_scenario.get('Monitors',[]) if isinstance(m,dict)]
scene_m=[m for m in mons if m.get('Target')=='scene_skip']
if len(scene_m)!=1:
    finding('HIGH','dungeon',f'expected exactly one scene_skip monitor, found {len(scene_m)}')
else:
    m=scene_m[0]
    if int(m.get('ScanIntervalMs',0))==1200 and int(m.get('CooldownMs',0))==2500:
        ok('dungeon','scene_skip monitor restored at 1200ms scan / 2500ms cooldown')
    else:
        finding('MEDIUM','dungeon',f'scene_skip timing changed: {m}')

scene=dby.get('scene_skip')
if scene:
    roi=scene.get('Roi') or {}
    full=(roi.get('X')==0 and roi.get('Y')==0 and roi.get('Width')==800 and roi.get('Height')==1000)
    th=float(scene.get('Threshold',1.0))
    mn=float(scene.get('TemplateScaleMin',1)); mx=float(scene.get('TemplateScaleMax',1))
    if full and th<=0.62 and mn<=0.5 and mx>=1.4:
        finding('MEDIUM','dungeon','scene_skip is a full-screen auto-click monitor with broad 0.5-1.4 scale search and 0.62 threshold; false-positive clicks remain a stability risk')

# Retry remains OCR-only: this is a single point of failure after UI changes.
retry=dby.get('retry')
if retry:
    if str(retry.get('Kind','')).lower()=='ocr':
        finding('MEDIUM','dungeon','retry/다시 하기 is OCR-only; another font/layout change can still stall step 4 and invoke recovery')
    if str(retry.get('Text',''))=='다시 하기' and int(retry.get('MaxEditDistance',0))>=2:
        ok('dungeon','retry OCR accepts updated spaced text with edit-distance tolerance')

for tid in ['policy_shutdown','policy_error88']:
    if tid not in dby:
        finding('HIGH','dungeon',f'{tid} safety target missing')
    elif str(dby[tid].get('Kind','')).lower()!='ocr':
        finding('MEDIUM','dungeon',f'{tid} is not OCR as expected')

engine_p=app/'dungeon/ScenarioEngine.cs'
engine=read(engine_p) if engine_p.exists() else ''
if not engine:
    finding('HIGH','dungeon','ScenarioEngine.cs missing/unreadable')
else:
    must=[
        'DUNGEON_SCREEN_FIRST_RECOVERY_V6',
        'ESC 없이 현재 화면 먼저 판별',
        '최후 수단 ESC 1회 입력 후 재판별',
        'DUNGEON_POLICY_SHUTDOWN_DETECTED',
        'DUNGEON_CHALLENGE_DISAMBIGUATION_V5',
        '던전 밖 HUD 3/4 이상 확인',
        '어비스 클릭 검증 실패',
    ]
    for marker in must:
        if marker not in engine:
            finding('HIGH','dungeon',f'missing expected engine marker: {marker}')
    if 'DUNGEON_UPDATE_20260917_MENU_FALLBACK' in engine:
        finding('HIGH','dungeon','old V0.1.27 second-ESC fallback is still present')

    # Check Smart Recovery input behavior.
    a=engine.find('private async Task<bool> TrySmartRecoveryAsync')
    b=engine.find('private async Task<bool> TryAbyssInternalRecoveryAsync', a)
    smart=engine[a:b] if a>=0 and b>a else ''
    esc_count=smart.count('TapScanCode(0x01)')
    if esc_count==1:
        ok('dungeon','non-Abyss Smart Recovery contains exactly one ESC send path per attempt')
    else:
        finding('HIGH','dungeon',f'non-Abyss Smart Recovery contains {esc_count} ESC send sites (expected 1)')

    # Important: policy gate is only in the recovery classifier, not global scenario monitors.
    detect_a=engine.find('private async Task<int?> DetectKnownDungeonRecoveryStepAsync')
    detect_b=engine.find('private async Task<bool> TrySmartRecoveryAsync', detect_a)
    detect=engine[detect_a:detect_b] if detect_a>=0 and detect_b>detect_a else ''
    if 'policy_shutdown' in detect and 'policy_error88' in detect:
        ok('dungeon','policy/ERROR88 gate executes during Smart Recovery classification')
    if not any(m.get('Target') in {'policy_shutdown','policy_error88'} for m in mons):
        finding('HIGH','dungeon','policy/ERROR88 detection is not a global monitor; during a long normal wait (e.g. 600s combat wait) shutdown can remain undetected until timeout, while other monitors may still run')

    # Recovery-attempt budget semantics: reset after any recognized-state recovery means repeated same-state stalls can continue forever.
    if 'recoveryFailures = 0;' in engine and '_resumeStepIndex = resumeStep.Value' in engine:
        # Narrow evidence: RunAsync resets recoveryFailures after recovered branch.
        run_a=engine.find('public async Task RunAsync')
        smart_a=engine.find('private async Task<bool> TrySmartRecoveryAsync')
        run=engine[run_a:smart_a] if run_a>=0 and smart_a>run_a else ''
        pattern=re.compile(r'if \(recovered\).*?recoveryFailures\s*=\s*0;', re.S)
        if pattern.search(run):
            finding('HIGH','dungeon','AutoRecoveryMaxAttempts limits only consecutive classifier failures; after a recognized screen recoveryFailures resets to 0, so repeated recover->same step timeout cycles can continue indefinitely')

    # Global monitor is invoked inside recovery classifier; it can click scene_skip before state classification.
    if 'CheckMonitorsAsync(frame, ct)' in detect and scene_m:
        finding('MEDIUM','dungeon','Smart Recovery classifier runs global monitors before state classification; scene_skip may click during recovery and mutate the screen being diagnosed')

    # Challenge safety semantics.
    if 'RequiredConsecutive = 3' in engine and 'challenge: do NOT click' in engine:
        ok('dungeon','entry guard requires stable challenge confirmation and does not click challenge state')
    else:
        finding('HIGH','dungeon','challenge confirmation/no-click guard markers not found')

# --- Input/cancellation/static loop audit across all C# ---
cs_files=list(app.rglob('*.cs'))
if not cs_files:
    finding('HIGH','source','no C# source files found')
else:
    ok('source',f'{len(cs_files)} C# files discovered')

for p in cs_files:
    text=read(p)
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if re.search(r'while\s*\(\s*true\s*\)|for\s*\(\s*;\s*;\s*\)', line):
            window='\n'.join(lines[i:i+45])
            if ('CancellationToken' not in window and 'ct.' not in window and 'IsCancellationRequested' not in window and 'break;' not in window):
                finding('MEDIUM','loops',f'{p.relative_to(root)}:{i+1} apparently unbounded loop without nearby cancellation/break')

# Input call inventory for review.
input_sites=[]
for p in cs_files:
    text=read(p)
    for name in ['ClickClientPoint(', 'TapScanCode(', 'TapVirtualKey(', 'KeyDown(', 'KeyUp(']:
        n=text.count(name)
        if n:
            input_sites.append(f'{p.relative_to(root)} {name} x{n}')
ok('input','; '.join(input_sites) if input_sites else 'no direct input calls found')

# F10 stop should remain in app code.
all_cs='\n'.join(read(p) for p in cs_files)
if 'F10' in all_cs or 'Keys.F10' in all_cs:
    ok('safety','F10 stop marker present in source')
else:
    finding('HIGH','safety','F10 stop marker not found in C# source')

# Check 5 MB log rollover markers heuristically.
if '5 * 1024 * 1024' in all_cs or '5*1024*1024' in all_cs or '5_000_000' in all_cs or '5242880' in all_cs:
    ok('logging','5MB-class log rollover constant found')
else:
    finding('LOW','logging','could not statically confirm 5MB log rollover constant')

# Fishing template integrity against previously validated known-good hashes.
known={
 'compass.png':'af26e115ad824262ec890e51bb072b74098278d7cdbc40c6f1e7381fb3c467c3',
 'gauge.png':'22d78ea16f21db75ff11cb7a576e3275204f051a4214f8791c9605d975a317f8',
 'healthbar.png':'b79c90379ff0558ab19f77ac28a5e2dd64928f3d0ec46b1ce3fc5906a7956373',
 'hook.png':'e584e44185e15edbb75c8505ea5002edcaf3c0e2e770d8f6417ba4ff4fde8949',
}
for name,expected in known.items():
    p=app/'templates'/name
    if not p.exists():
        finding('HIGH','fishing',f'missing template {name}')
    else:
        actual=sha256(p)
        if actual!=expected:
            finding('HIGH','fishing',f'{name} hash changed: {actual}')
        else:
            ok('fishing',f'{name} hash unchanged')

# Version consistency.
ver_hits=[]
for p in list(app.rglob('*.cs'))+list(app.rglob('*.csproj'))+list(app.rglob('*.json')):
    try: t=read(p)
    except: continue
    if '0.1.' in t or 'V0.1.' in t:
        vals=sorted(set(re.findall(r'V?0\.1\.\d+(?:\.0)?', t)))
        if vals: ver_hits.append((str(p.relative_to(root)), vals))
old=[(p,v) for p,v in ver_hits if any(('0.1.28' not in x) for x in v)]
if old:
    finding('LOW','version',f'older version strings remain in runtime tree: {old[:8]}'+(' ...' if len(old)>8 else ''))
else:
    ok('version','no conflicting runtime version strings found in scanned files')

# Report.
rank={'HIGH':0,'MEDIUM':1,'LOW':2}
findings.sort(key=lambda x:(rank.get(x[0],9),x[1],x[2]))
counts={s:sum(1 for f in findings if f[0]==s) for s in ['HIGH','MEDIUM','LOW']}
print('=== V0.1.28 FULL STABILITY AUDIT ===')
print(f'ROOT={root}')
print(f'CHECKS_OK={len(checks)} HIGH={counts["HIGH"]} MEDIUM={counts["MEDIUM"]} LOW={counts["LOW"]}')
print('\n--- FINDINGS ---')
if not findings:
    print('NONE')
else:
    for sev,area,msg in findings:
        print(f'[{sev}] [{area}] {msg}')
print('\n--- PASSED / OBSERVED ---')
for area,msg in checks:
    print(f'[OK] [{area}] {msg}')
print('\n--- END AUDIT ---')
