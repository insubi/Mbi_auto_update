#!/usr/bin/env python3
import json, pathlib, sys
root=pathlib.Path(sys.argv[1]).resolve()

def rw(rel, fn, bom=True):
    p=root/rel
    s=p.read_text(encoding='utf-8-sig')
    n=fn(s)
    if n==s: raise SystemExit(f'No change made: {rel}')
    p.write_text(n, encoding='utf-8-sig' if bom else 'utf-8')

def rep(rel, old, new):
    def f(s):
        if old not in s: raise SystemExit(f'Expected text not found: {rel}')
        return s.replace(old,new)
    rw(rel,f)

rep('FishingAutomation/UpdateManager.cs','public const string CurrentVersion = "v30";','public const string CurrentVersion = "v31";')
rep('FishingAutomation/UpdateManager.cs','new ProductInfoHeaderValue("MabiAuto", "30")','new ProductInfoHeaderValue("MabiAuto", "31")')
rep('FishingAutomation/FishingAutomation.csproj','<Version>30.0.0</Version>','<Version>31.0.0</Version>')
rep('FishingAutomation/FishingAutomation.csproj','<AssemblyVersion>30.0.0.0</AssemblyVersion>','<AssemblyVersion>31.0.0.0</AssemblyVersion>')
rep('FishingAutomation/FishingAutomation.csproj','<FileVersion>30.0.0.0</FileVersion>','<FileVersion>31.0.0.0</FileVersion>')
rep('FishingAutomation/MainForm.cs',' · v30"',' · v31"')
rep('FishingAutomation/MainForm.Dashboard.cs','Dashboard v30','Dashboard v31')
rep('FishingAutomation/MainForm.Dashboard.cs','v30  |  Mabi Auto','v31  |  Mabi Auto')

rep('FishingAutomation/Dungeon/Models.cs',
'''    public int CooldownMs { get; set; } = 1000;\n}''',
'''    public int CooldownMs { get; set; } = 1000;\n    // Heavy OCR monitors do not need to run on every captured frame.\n    // 0 keeps the previous behavior; otherwise detection is throttled per target.\n    public int ScanIntervalMs { get; set; } = 0;\n}''')

rep('FishingAutomation/Dungeon/ScenarioEngine.cs',
'''    private readonly Dictionary<string, long> _monitorLastAction = new(StringComparer.OrdinalIgnoreCase);\n    private int _cycle;''',
'''    private readonly Dictionary<string, long> _monitorLastAction = new(StringComparer.OrdinalIgnoreCase);\n    private readonly Dictionary<string, long> _monitorLastScan = new(StringComparer.OrdinalIgnoreCase);\n    private int _cycle;''')

def engine_calls(s):
    old='''            await CheckMonitorsAsync(frame, ct);\n\n            // 선택됨이 보이면 절대로 입장하지 않는다.'''
    if old not in s: raise SystemExit('challenge monitor call not found')
    s=s.replace(old,'''            if (await CheckMonitorsAsync(frame, ct))\n            {\n                consecutive = 0;\n                continue;\n            }\n\n            // 선택됨이 보이면 절대로 입장하지 않는다.''',1)
    old='''            await CheckMonitorsAsync(finalFrame, ct);\n\n            // 마지막 순간에 선택됨이면 입장 금지.'''
    if old not in s: raise SystemExit('final monitor call not found')
    s=s.replace(old,'''            if (await CheckMonitorsAsync(finalFrame, ct))\n            {\n                consecutive = 0;\n                continue;\n            }\n\n            // 마지막 순간에 선택됨이면 입장 금지.''',1)
    old='''            await CheckMonitorsAsync(frame, ct);\n\n            var found = await _detector.DetectAsync(step.Target, frame, ct);'''
    if old not in s: raise SystemExit('step monitor call not found')
    s=s.replace(old,'''            if (await CheckMonitorsAsync(frame, ct))\n                continue;\n\n            var found = await _detector.DetectAsync(step.Target, frame, ct);''',1)
    old='''            await CheckMonitorsAsync(frame, ct);\n\n            var found = await _detector.DetectAsync(targetId, frame, ct);'''
    if old not in s: raise SystemExit('timeout monitor call not found')
    return s.replace(old,'''            if (await CheckMonitorsAsync(frame, ct))\n                continue;\n\n            var found = await _detector.DetectAsync(targetId, frame, ct);''',1)
rw('FishingAutomation/Dungeon/ScenarioEngine.cs', engine_calls)

old='''    private async Task CheckMonitorsAsync(Bitmap frame, CancellationToken ct)\n    {\n        foreach (var m in _scenario.Monitors)\n        {\n            var r = await _detector.DetectAsync(m.Target, frame, ct);\n            if (!r.Found) continue;\n\n            long now = Environment.TickCount64;\n            if (_monitorLastAction.TryGetValue(m.Target, out var last) && now - last < m.CooldownMs) continue;\n            _monitorLastAction[m.Target] = now;\n\n            switch (m.Action.ToLowerInvariant())\n            {\n                case "click":\n                    Log?.Invoke($"[monitor] {m.Target} 발견 → 클릭");\n                    _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                    _input.ClickClientPoint(_hwnd, r.Center);\n                    break;\n                case "restart_cycle":\n                    Log?.Invoke($"[monitor] {m.Target} 발견 → 현재 판 재시작");\n                    throw new RestartCycleException();\n                case "stop":\n                    throw new OperationCanceledException($"감시 타깃 '{m.Target}' 발견으로 정지");\n                default:\n                    throw new InvalidOperationException($"알 수 없는 monitor action: {m.Action}");\n            }\n        }\n    }'''
new='''    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)\n    {\n        foreach (var m in _scenario.Monitors)\n        {\n            long now = Environment.TickCount64;\n\n            if (_monitorLastAction.TryGetValue(m.Target, out var lastAction) &&\n                now - lastAction < Math.Max(0, m.CooldownMs))\n                continue;\n\n            int scanInterval = Math.Max(0, m.ScanIntervalMs);\n            if (scanInterval > 0 &&\n                _monitorLastScan.TryGetValue(m.Target, out var lastScan) &&\n                now - lastScan < scanInterval)\n                continue;\n            _monitorLastScan[m.Target] = now;\n\n            var r = await _detector.DetectAsync(m.Target, frame, ct);\n            if (!r.Found) continue;\n\n            _monitorLastAction[m.Target] = Environment.TickCount64;\n            switch (m.Action.ToLowerInvariant())\n            {\n                case "click":\n                    Log?.Invoke($"[monitor] {m.Target} 발견 → 클릭 ({r.ReadText ?? r.Score.ToString("0.000")}) @ {r.Bounds}");\n                    _hwnd = await ResolveRequiredGameWindowAsync(ct);\n                    NativeMethods.SetForegroundWindow(_hwnd);\n                    _input.ClickClientPoint(_hwnd, r.Center);\n                    await Task.Delay(_settings.ClickSettleMs, ct);\n                    return true;\n                case "restart_cycle":\n                    Log?.Invoke($"[monitor] {m.Target} 발견 → 현재 판 재시작");\n                    throw new RestartCycleException();\n                case "stop":\n                    throw new OperationCanceledException($"감시 타깃 '{m.Target}' 발견으로 정지");\n                default:\n                    throw new InvalidOperationException($"알 수 없는 monitor action: {m.Action}");\n            }\n        }\n        return false;\n    }'''
rep('FishingAutomation/Dungeon/ScenarioEngine.cs',old,new)

scene={'Id':'scene_skip','Kind':'ocr','Roi':{'X':0,'Y':0,'Width':800,'Height':1000},'Text':'장면 넘기기','MaxEditDistance':1,'OcrRetryAt2x':True}
mon={'Target':'scene_skip','Action':'click','CooldownMs':2500,'ScanIntervalMs':1200}
for rel in ['FishingAutomation/dungeon/config/targets.json','FishingAutomation/abyss/config/targets.json','FishingAutomation/dungeon_config/targets.json']:
    p=root/rel; data=json.loads(p.read_text(encoding='utf-8-sig'))
    data=[x for x in data if not (isinstance(x,dict) and x.get('Id')=='scene_skip')]; data.append(scene)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for rel in ['FishingAutomation/dungeon/config/scenario.json','FishingAutomation/abyss/config/scenario.json','FishingAutomation/dungeon_config/scenario.json']:
    p=root/rel; data=json.loads(p.read_text(encoding='utf-8-sig'))
    data['Monitors']=[m for m in data.get('Monitors',[]) if m.get('Target')!='scene_skip']+[mon]
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

(root/'CHANGES_v31_SCENE_SKIP.txt').write_text('''MABI AUTO v31 - 장면 넘기기 자동 클릭\n\n- 던전/어비스 진행 중 한국어 OCR로 "장면 넘기기" 자동 감지 후 클릭\n- 1.2초 간격 OCR 감시, 클릭 후 2.5초 쿨다운\n- 클릭 뒤 기존 캡처 화면을 재사용하지 않고 새 화면으로 다음 단계 진행\n- 800x1000 전체 화면에서 OCR 오차 1글자 허용, 2배 확대 재시도\n''',encoding='utf-8-sig')
(root/'START_HERE_v31.txt').write_text('''MABI AUTO v31\n\n권장: GitHub Release의 MabiAuto_v31_Windows_Lite.zip 사용\n.NET SDK 설치 불필요\n\n신규: 던전/어비스 진행 중 "장면 넘기기" 자동 OCR 클릭\n기존 v30 사용자는 프로그램 업데이트 기능으로 v31 업데이트 가능\n''',encoding='utf-8-sig')
print('v31 scene-skip overlay applied')