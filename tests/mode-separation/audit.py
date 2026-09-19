from pathlib import Path
import hashlib,json,re,sys
baseline=Path(sys.argv[1])/'FishingAutomation'; current=Path(sys.argv[2])/'FishingAutomation'
changed=[]
for p in current.rglob('*'):
 if not p.is_file() or {'bin','obj'} & set(p.relative_to(current).parts): continue
 q=baseline/p.relative_to(current)
 if not q.exists() or p.read_bytes()!=q.read_bytes(): changed.append(str(p.relative_to(current)))
expected={'MainForm.cs','MainForm.ReferenceUI.cs','MainForm.Dashboard.cs','abyss/config/scenario.json','dungeon/ScenarioEngine.cs','dungeon/IScenarioRunner.cs','dungeon/PeacaRouteEngine.cs','dungeon/ScenarioEngine.AbyssRetry.cs','dungeon/AbyssResultLayout.cs'}
assert set(changed)==expected,(changed,expected)
engine=(current/'dungeon/ScenarioEngine.cs').read_text();old=(baseline/'dungeon/ScenarioEngine.cs').read_text();peaca=(current/'dungeon/PeacaRouteEngine.cs').read_text();main=(current/'MainForm.cs').read_text()
# Methods whose behavior must be preserved byte-for-byte.
def section(text,start,end): return text[text.index(start):text.index(end,text.index(start))]
for start,end in [
 ('    private async Task VerifyChallengeBeforeEntryAsync','    private async Task<bool> VerifyAbyssSelectionScreenAsync'),
 ('    private async Task<bool> VerifyAbyssSelectionScreenAsync','    private async Task ExecuteStepAsync'),
 ('    private async Task AdvanceAbyssClearScreenAsync','    private async Task<bool> DetectAbyssOutsideWorkflowAsync')]:
 assert section(old,start,end)==section(engine,start,end),start
oldmain=(baseline/'MainForm.cs').read_text()
# The full fishing start and stop implementation is unchanged.
assert section(oldmain,'    private void StartFishing()','    private async Task StartScenarioAsync')==section(main,'    private void StartFishing()','    private async Task StartScenarioAsync')
assert 'RunDungeonPreRouteAsync' not in engine and '_preRoute' not in engine
assert 'ScenarioEngine' not in peaca and 'CheckMonitorsAsync' not in peaca and 'VerifyChallengeBeforeEntryAsync' not in peaca
assert '_input.ClickClientPoint(_hwnd, new Point(493, 952));' in peaca
assert 'frame.Width != 800 || frame.Height != 1000' in peaca
assert 'ready >= 2' in peaca
assert '_resumeStepIndex = IsAbyss ? AbyssCombatStepIndex : 0;' in engine
assert 'modeName == "페카 심층"\n                ? new PeacaRouteEngine' in main
orig=json.loads((baseline/'abyss/config/scenario.json').read_text());new=json.loads((current/'abyss/config/scenario.json').read_text())
assert orig['Steps'][:5]==new['Steps'][:5]
assert orig['Monitors']==new['Monitors']
assert new['Steps'][5]['Target']=='abyss_result_retry' and len(new['Steps'])==6
ui=(current/'MainForm.ReferenceUI.cs').read_text();old_ui=(baseline/'MainForm.ReferenceUI.cs').read_text()
assert re.findall(r'^.*AddButton\(.*$',ui,re.M)==re.findall(r'^.*AddButton\(.*$',old_ui,re.M)
# All unlisted source/assets (including ROI configs and Interception) are byte-identical above.
print(json.dumps({'status':'PASS','base':'V0.1.48 e567f6e454a3ee3aea2099ee116a8b1a894d57a5','changed_files':sorted(changed),'checks':['unchanged fishing and input files','unchanged regular entry verifier','unchanged Abyss first five steps and monitors','unchanged UI buttons and layout','Peaca owns separate input/detector/state and no recovery calls','client (493,952) gated by size and two confirmed frames','Abyss retry resumes combat step instead of initial selection']},ensure_ascii=False,indent=2))
