#!/usr/bin/env python3
from pathlib import Path
import json, re, sys
root = Path(sys.argv[1]).resolve()
app = root / 'FishingAutomation'
print('=== V75 INSPECT START ===')
for rel in ['dungeon/ScenarioEngine.cs','MainForm.cs','dungeon/TemplateMatcher.cs','abyss/config/targets.json']:
    p = app / rel
    print(f'--- FILE {rel} ---')
    text = p.read_text(encoding='utf-8-sig')
    if rel.endswith('ScenarioEngine.cs'):
        keys = ['abyss_touch_screen','TryAbyssInternalRecoveryAsync','강제 퇴장 완료','abyss_exit','SaveDebug','PruneDebug']
        for key in keys:
            i = text.find(key)
            if i >= 0:
                a=max(0,i-2600); b=min(len(text),i+7000)
                print(f'### {key} @ {i} ###')
                print(text[a:b])
    elif rel.endswith('MainForm.cs'):
        for key in ['private void CheckAutoStop()','_autoStopLastTriggeredDate']:
            i=text.find(key)
            if i>=0:
                print(f'### {key} @ {i} ###')
                print(text[max(0,i-1800):min(len(text),i+4500)])
    elif rel.endswith('TemplateMatcher.cs'):
        for key in ['bestScore','DetectionResult.NotFound']:
            i=text.find(key)
            if i>=0:
                print(f'### {key} @ {i} ###')
                print(text[max(0,i-1200):min(len(text),i+3200)])
    else:
        targets=json.loads(text)
        wanted={'abyss_menu','abyss_icon','abyss_leave_dungeon','abyss_exit','abyss_touch_screen','abyss_dungeon_clear_visual','scene_skip','abyss_popup_close'}
        print(json.dumps([t for t in targets if t.get('Id') in wanted], ensure_ascii=False, indent=2))
print('=== V75 INSPECT END ===')
raise SystemExit('V75 inspect-only pass: intentional stop before release')
