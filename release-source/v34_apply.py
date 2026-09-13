#!/usr/bin/env python3
import pathlib, sys

root = pathlib.Path(sys.argv[1]).resolve()


def patch(rel, old, new):
    p = root / rel
    s = p.read_text(encoding='utf-8-sig')
    if old not in s:
        raise SystemExit('patch marker missing: ' + rel)
    p.write_text(s.replace(old, new, 1), encoding='utf-8-sig')

patch(
    'FishingAutomation/UpdateManager.cs',
    'public const string CurrentVersion = "v33";',
    'public const string CurrentVersion = "v34";'
)

patch(
    'FishingAutomation/MainForm.cs',
    'Text = "MABI AUTO · 마비노기 모바일 매크로 · v33";',
    'Text = "MABI AUTO · v34";'
)

patch(
    'FishingAutomation/MainForm.Life.cs',
    'Text = "양털 목표 수량",',
    'Text = "양털 목표 수량 (1~9999)",'
)

(root / 'CHANGES_v34_WINDOW_TITLE_WOOL_TARGET.txt').write_text(
    'MABI AUTO v34\n'
    '- 매크로 창 제목에서 "마비노기 모바일" 문구 제거\n'
    '- 매크로 창 제목: MABI AUTO · v34\n'
    '- 생활 > 옷감 가공 양털 목표 수량 입력 범위 1~9999 유지 및 UI에 범위 명시\n'
    '- 기존 낚시/던전/어비스/생활 기능 유지\n',
    encoding='utf-8'
)

print('Applied v34 window-title and wool-target update')
