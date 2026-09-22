#!/usr/bin/env python3
from pathlib import Path
import json
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def load_json(path: Path):
    return json.loads(read(path))

def save_json(path: Path, value) -> None:
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

# ---------------------------------------------------------------------------
# 1) Abyss scene-skip: keep two-frame runtime confirmation, but repair the
#    detector for the current top-right "장면 넘기기" button.
#    Do not add "대화 넘기기".
# ---------------------------------------------------------------------------
targets_path = app / "abyss" / "config" / "targets.json"
targets = load_json(targets_path)

scene = next((t for t in targets if t.get("Id") == "scene_skip"), None)
if scene is None:
    raise SystemExit("abyss scene_skip target missing")
scene["Kind"] = "hybrid"
scene["Roi"] = {"X": 580, "Y": 0, "Width": 220, "Height": 140}
scene["Text"] = "장면 넘기기"
scene["MaxEditDistance"] = 1
scene["OcrRetryAt2x"] = True
scene["Threshold"] = 0.62
scene["TemplateScaleMin"] = 0.50
scene["TemplateScaleMax"] = 1.40
scene["TemplateScaleStep"] = 0.08

# ---------------------------------------------------------------------------
# 2) Abyss death detection.
#    Death is only considered valid when BOTH "행동불능" and "여기서 부활"
#    are visible on two consecutive captures. We intentionally never click
#    the revive button and never inspect/click the feather/purchase path.
# ---------------------------------------------------------------------------
for id_ in ("abyss_death_state", "abyss_revive_here", "abyss_exit_confirm_title"):
    targets = [t for t in targets if t.get("Id") != id_]

targets.extend([
    {
        "Id": "abyss_death_state",
        "Kind": "ocr",
        "Roi": {"X": 180, "Y": 100, "Width": 440, "Height": 330},
        "Text": "행동불능",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True
    },
    {
        "Id": "abyss_revive_here",
        "Kind": "ocr",
        "Roi": {"X": 150, "Y": 700, "Width": 500, "Height": 240},
        "Text": "여기서 부활",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True
    },
    {
        "Id": "abyss_exit_confirm_title",
        "Kind": "ocr",
        "Roi": {"X": 120, "Y": 620, "Width": 560, "Height": 220},
        "Text": "던전에서 퇴장하시겠습니까",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True
    }
])
save_json(targets_path, targets)

scenario_path = app / "abyss" / "config" / "scenario.json"
scenario = load_json(scenario_path)
monitors = [m for m in scenario.get("Monitors", [])
            if m.get("Target") != "abyss_death_state"]

death_monitor = {
    "Target": "abyss_death_state",
    "Action": "abyss_death_exit",
    "CooldownMs": 10000,
    "ScanIntervalMs": 500
}

# Keep potion safety monitors first, then death, then scene skip/others.
insert_at = 0
for i, m in enumerate(monitors):
    if m.get("Target") in ("abyss_potion_popup_title", "abyss_popup_close"):
        insert_at = i + 1
monitors.insert(insert_at, death_monitor)
scenario["Monitors"] = monitors
save_json(scenario_path, scenario)

# ---------------------------------------------------------------------------
# 3) Runtime: death -> no revive -> verified leave icon -> verified exit dialog
#    -> exit -> outside HUD -> restart scenario from step 1.
#    This path does not call CheckMonitorsAsync recursively.
# ---------------------------------------------------------------------------
engine_path = app / "dungeon" / "ScenarioEngine.cs"
engine = read(engine_path)

check_anchor = "    private async Task<bool> CheckMonitorsAsync(Bitmap frame, CancellationToken ct)\n"
if check_anchor not in engine:
    raise SystemExit("CheckMonitorsAsync anchor missing")

helper = r'''    // V0162_ABYSS_DEATH_EXIT_NO_REVIVE
    // On a confirmed death screen we never click "여기서 부활".
    // We use the existing verified Abyss leave control, verify the exit dialog,
    // click its detected "나가기" button, verify outside HUD, then restart step 1.
    private async Task HandleAbyssDeathExitAsync(CancellationToken ct)
    {
        Log?.Invoke("[어비스 사망] 부활 사용 안 함 -> 던전 퇴장 절차 시작");

        for (int attempt = 1; attempt <= 2; attempt++)
        {
            ct.ThrowIfCancellationRequested();

            using (var frame = await CaptureGameWindowAsync(ct))
            {
                var leave = await _detector.DetectAsync("abyss_leave_dungeon", frame, ct);
                if (!leave.Found)
                {
                    Log?.Invoke($"[어비스 사망] 던전 나가기 아이콘 미검출 {attempt}/2");
                    await Task.Delay(450, ct);
                    continue;
                }

                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                Log?.Invoke($"[어비스 사망] 던전 나가기 클릭 {attempt}/2 @ {leave.Bounds}");
                _input.ClickClientPoint(_hwnd, leave.Center);
            }

            var dialogTimer = Stopwatch.StartNew();
            while (dialogTimer.Elapsed < TimeSpan.FromSeconds(5))
            {
                ct.ThrowIfCancellationRequested();
                await Task.Delay(250, ct);

                using var dialogFrame = await CaptureGameWindowAsync(ct);
                var title = await _detector.DetectAsync("abyss_exit_confirm_title", dialogFrame, ct);
                var exit = await _detector.DetectAsync("abyss_exit", dialogFrame, ct);

                if (!title.Found || !exit.Found)
                    continue;

                Log?.Invoke($"[어비스 사망] 퇴장 확인창 확인 -> 나가기 클릭 @ {exit.Bounds}");
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                NativeMethods.SetForegroundWindow(_hwnd);
                _input.ClickClientPoint(_hwnd, exit.Center);
                await Task.Delay(Math.Max(700, _settings.ClickSettleMs), ct);

                try
                {
                    await WaitForAbyssHomeAfterNormalExitAsync(ct);
                }
                catch (TimeoutException ex)
                {
                    await SaveRecoveryScreenshotAsync("abyss_death_outside_timeout", ct);
                    throw new InvalidOperationException(
                        "사망 후 나가기는 눌렀지만 던전 밖 HUD를 확인하지 못해 안전 정지합니다.", ex);
                }

                Log?.Invoke("[어비스 사망] 던전 밖 복귀 확인 완료 -> 어비스 처음부터 재시작");
                return;
            }

            Log?.Invoke($"[어비스 사망] 퇴장 확인창 미확인 {attempt}/2 -> 던전 나가기 제한 재시도");
        }

        await SaveRecoveryScreenshotAsync("abyss_death_exit_failed", ct);
        throw new InvalidOperationException(
            "사망 후 던전 퇴장 확인창을 확인하지 못해 부활/구매 입력 없이 안전 정지합니다.");
    }

'''
engine = engine.replace(check_anchor, helper + check_anchor, 1)

detect_anchor = '''            var r = await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
'''
death_block = '''            var r = await _detector.DetectAsync(m.Target, frame, ct);
            if (!r.Found) continue;

            if (m.Target.Equals("abyss_death_state", StringComparison.OrdinalIgnoreCase))
            {
                var revive = await _detector.DetectAsync("abyss_revive_here", frame, ct);
                if (!revive.Found)
                    continue;

                Log?.Invoke("[어비스 사망] 행동불능 + 여기서 부활 후보 1/2 -> 별도 프레임 재확인");
                await Task.Delay(250, ct);

                using var deathConfirmFrame = await CaptureGameWindowAsync(ct);
                var deathConfirm = await _detector.DetectAsync("abyss_death_state", deathConfirmFrame, ct);
                var reviveConfirm = await _detector.DetectAsync("abyss_revive_here", deathConfirmFrame, ct);

                if (!deathConfirm.Found || !reviveConfirm.Found)
                {
                    Log?.Invoke("[어비스 사망] 2차 확인 실패 -> 아무 입력도 하지 않음");
                    continue;
                }

                _monitorLastAction[m.Target] = Environment.TickCount64;
                Log?.Invoke("[어비스 사망] 행동불능 + 여기서 부활 2/2 확인 -> 부활하지 않고 퇴장");
                await HandleAbyssDeathExitAsync(ct);
                throw new RestartCycleException();
            }

            if (m.Target.Equals("scene_skip", StringComparison.OrdinalIgnoreCase))
'''
if detect_anchor not in engine:
    raise SystemExit("monitor detection anchor missing")
engine = engine.replace(detect_anchor, death_block, 1)
write(engine_path, engine)

# ---------------------------------------------------------------------------
# 4) Version metadata.
# ---------------------------------------------------------------------------
project_path = app / "FishingAutomation.csproj"
project = read(project_path)
for old, new in (
    ("<Version>0.1.61</Version>", "<Version>0.1.62</Version>"),
    ("<AssemblyVersion>0.1.61.0</AssemblyVersion>", "<AssemblyVersion>0.1.62.0</AssemblyVersion>"),
    ("<FileVersion>0.1.61.0</FileVersion>", "<FileVersion>0.1.62.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update_path = app / "UpdateManager.cs"
update = read(update_path)
if 'CurrentVersion = "V0.1.61"' not in update:
    raise SystemExit("UpdateManager V0.1.61 marker missing")
update = update.replace('CurrentVersion = "V0.1.61"', 'CurrentVersion = "V0.1.62"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 5) Static invariants: protect V0.1.61 fixes and verify the new behavior.
# ---------------------------------------------------------------------------
engine = read(engine_path)
scenario = load_json(scenario_path)
targets = load_json(targets_path)

required_engine = (
    "V0162_ABYSS_DEATH_EXIT_NO_REVIVE",
    "행동불능 + 여기서 부활 후보 1/2",
    "행동불능 + 여기서 부활 2/2 확인 -> 부활하지 않고 퇴장",
    'DetectAsync("abyss_exit_confirm_title"',
    'DetectAsync("abyss_leave_dungeon"',
    "던전 밖 복귀 확인 완료 -> 어비스 처음부터 재시작",
    "실제 결과 화면 후보 1/2",
    "실제 결과 화면 2/2 확인",
    "회복 물약 팝업 ESC 후 닫힘 2프레임 확인",
)
for marker in required_engine:
    if marker not in engine:
        raise SystemExit(f"required runtime marker missing: {marker}")

# Explicitly ensure the new death path never clicks the revive target.
helper_text = engine[engine.index("V0162_ABYSS_DEATH_EXIT_NO_REVIVE"):engine.index(check_anchor)]
if 'ClickClientPoint' in helper_text and 'abyss_revive_here' in helper_text:
    raise SystemExit("revive target must never be clicked")

scene = next(t for t in targets if t.get("Id") == "scene_skip")
if scene.get("Kind") != "hybrid" or scene.get("Text") != "장면 넘기기":
    raise SystemExit("abyss scene_skip OCR+template repair missing")
if scene.get("Roi") != {"X": 580, "Y": 0, "Width": 220, "Height": 140}:
    raise SystemExit("abyss scene_skip ROI mismatch")

death = next(t for t in targets if t.get("Id") == "abyss_death_state")
revive = next(t for t in targets if t.get("Id") == "abyss_revive_here")
exit_title = next(t for t in targets if t.get("Id") == "abyss_exit_confirm_title")
if death.get("Text") != "행동불능" or revive.get("Text") != "여기서 부활":
    raise SystemExit("death/revive OCR targets invalid")
if exit_title.get("Text") != "던전에서 퇴장하시겠습니까":
    raise SystemExit("exit confirmation title OCR target invalid")

dm = [m for m in scenario.get("Monitors", []) if m.get("Target") == "abyss_death_state"]
if len(dm) != 1 or dm[0].get("Action") != "abyss_death_exit":
    raise SystemExit("death monitor missing or invalid")

if "<Version>0.1.62</Version>" not in read(project_path):
    raise SystemExit("project version not V0.1.62")
if 'CurrentVersion = "V0.1.62"' not in read(update_path):
    raise SystemExit("updater version not V0.1.62")

print("V0.1.62 applied: Abyss death=no revive->verified exit/restart + scene-skip OCR repair")
