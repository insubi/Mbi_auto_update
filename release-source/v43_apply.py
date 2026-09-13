#!/usr/bin/env python3
from pathlib import Path
import re, sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def repl(path, old, new, count=1):
    s = path.read_text(encoding="utf-8-sig")
    if old not in s:
        raise RuntimeError(f"pattern not found in {path}: {old[:120]}")
    path.write_text(s.replace(old, new, count), encoding="utf-8-sig")

repl(app / "UpdateManager.cs",
     'public const string CurrentVersion = "v42";',
     'public const string CurrentVersion = "v43";')

p = app / "MainForm.cs"
s = p.read_text(encoding="utf-8-sig")
s = s.replace('Text = "MABI AUTO · v42";', 'Text = "MABI AUTO · v43";', 1)
p.write_text(s, encoding="utf-8-sig")

p = app / "Dungeon" / "ScenarioEngine.cs"
s = p.read_text(encoding="utf-8-sig")
old = '''                    _input.ClickClientPoint(_hwnd, found.Center);
                    await Task.Delay(_settings.ClickSettleMs, ct);'''
new = '''                    _input.ClickClientPoint(_hwnd, found.Center);
                    await Task.Delay(_settings.ClickSettleMs, ct);

                    if (step.Target.Equals("abyss_exit", StringComparison.OrdinalIgnoreCase))
                        await WaitForAbyssHomeAfterNormalExitAsync(ct);'''
if old not in s:
    raise RuntimeError("ScenarioEngine normal click block not found")
s = s.replace(old, new, 1)

marker = '''    private async Task ClickTargetWithTimeoutAsync(
'''
helper = '''    private async Task WaitForAbyssHomeAfterNormalExitAsync(CancellationToken ct)
    {
        Log?.Invoke("[어비스] 나가기 클릭 완료 -> 던전 밖 복귀 확인 중");
        var sw = Stopwatch.StartNew();

        while (sw.Elapsed < TimeSpan.FromSeconds(60))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var home = await _detector.DetectAsync("abyss_menu", frame, ct);
            if (home.Found)
            {
                Log?.Invoke("[어비스] 던전 밖 복귀 확인 완료 -> 다음 입장 준비");
                return;
            }

            await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
        }

        Log?.Invoke("[어비스] 던전 밖 복귀 확인 시간초과 -> 다음 판에서 메뉴 재탐색");
    }

'''
if marker not in s:
    raise RuntimeError("ScenarioEngine helper insertion marker not found")
s = s.replace(marker, helper + marker, 1)
p.write_text(s, encoding="utf-8-sig")

p = app / "MainForm.Dashboard.cs"
s = p.read_text(encoding="utf-8-sig")
needle = '''        if (text.Contains("퇴장 절차 시작")) { _timeoutExits++; _stageStartedAt = null; SetStatus("10분 제한 초과 · 퇴장 중", Color.Orange); }
'''
insert = '''        if (text.Contains("퇴장 절차 시작")) { _timeoutExits++; _stageStartedAt = null; SetStatus("10분 제한 초과 · 퇴장 중", Color.Orange); }
        if (text.Contains("나가기 클릭 완료")) { _stageStartedAt = null; SetStatus("던전 밖 복귀 확인 중", Blue); }
        if (text.Contains("던전 밖 복귀 확인 완료")) { _stageStartedAt = null; SetStatus("완료 · 다음 입장 준비", Green); }
'''
if needle not in s:
    raise RuntimeError("Dashboard exit status marker not found")
s = s.replace(needle, insert, 1)
s = s.replace('Dashboard v42', 'Dashboard v43')
s = s.replace('Text = "v42  |  Mabi Auto"', 'Text = "v43  |  Mabi Auto"')
p.write_text(s, encoding="utf-8-sig")

p = app / "FishingAutomation.csproj"
s = p.read_text(encoding="utf-8-sig")
for k,v in {"Version":"43.0.0","AssemblyVersion":"43.0.0.0","FileVersion":"43.0.0.0"}.items():
    s = re.sub(rf'<{k}>[^<]+</{k}>', f'<{k}>{v}</{k}>', s, count=1)
p.write_text(s, encoding="utf-8-sig")

print("v43 normal abyss exit confirmation patch applied")
