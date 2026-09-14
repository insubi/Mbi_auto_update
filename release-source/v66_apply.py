#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve()

def show(rel, needles, radius=1800):
    p=root/rel
    s=p.read_text(encoding='utf-8-sig', errors='replace')
    print(f'===== {rel} =====')
    for needle in needles:
        i=s.find(needle)
        print(f'--- NEEDLE {needle!r} @ {i} ---')
        if i>=0:
            print(s[max(0,i-radius):min(len(s),i+radius)])

show('FishingAutomation/MainForm.ReferenceUI.cs', ['class ReferenceDashboard', 'ReferenceDashboard(MainForm owner)', '시스템 상태', 'v65.0.0 · UI'])
show('FishingAutomation/MainForm.cs', ['private readonly System.Windows.Forms.Timer _uiTimer', '_uiTimer.Tick', 'private void StopSelected()', 'public MainForm()'])
show('FishingAutomation/MainForm.Dashboard.cs', ['void UpdateDashboard', 'AnyRunning'])
print('V66_UI_INSPECT_END')
raise SystemExit(66)
