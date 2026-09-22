#!/usr/bin/env python3
from pathlib import Path
import json
import shutil
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
# 1) Recovery-potion popup: never click the purchase UI.
#    A monitor action named "escape" verifies the same target twice, sends
#    exactly one ESC, then requires the popup to disappear on two frames.
# ---------------------------------------------------------------------------
engine_path = app / "dungeon" / "ScenarioEngine.cs"
engine = read(engine_path)

anchor = '''                case "click":
                    Log?.Invoke($"[monitor] {m.Target} 발견 → 클릭 ({r.ReadText ?? r.Score.ToString("0.000")}) @ {r.Bounds}");
                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    _input.ClickClientPoint(_hwnd, r.Center);
                    await Task.Delay(_settings.ClickSettleMs, ct);
                    return true;
'''
escape_case = '''                case "escape":
                {
                    // POTION_POPUP_ESC_V1
                    // Never click a purchase/close coordinate from this monitor.
                    // Confirm the same popup on a fresh frame, press ESC exactly once,
                    // then prove that the popup disappeared before normal flow resumes.
                    Log?.Invoke($"[monitor] {m.Target} 1/2 확인 -> ESC 닫기 재확인");
                    await Task.Delay(180, ct);
                    using (var confirmFrame = await CaptureGameWindowAsync(ct))
                    {
                        var confirm = await _detector.DetectAsync(m.Target, confirmFrame, ct);
                        if (!confirm.Found)
                        {
                            Log?.Invoke($"[monitor] {m.Target} 2차 확인에서 사라짐 -> 입력 없이 진행");
                            return true;
                        }
                    }

                    _hwnd = await ResolveRequiredGameWindowAsync(ct);
                    NativeMethods.SetForegroundWindow(_hwnd);
                    Log?.Invoke($"[monitor] {m.Target} 2/2 확인 -> ESC 1회로 닫기 (구매 버튼 클릭 금지)");
                    _input.TapScanCode(0x01);

                    var closeTimer = Stopwatch.StartNew();
                    int goneFrames = 0;
                    while (closeTimer.Elapsed < TimeSpan.FromSeconds(4))
                    {
                        ct.ThrowIfCancellationRequested();
                        await Task.Delay(180, ct);
                        using var afterEsc = await CaptureGameWindowAsync(ct);
                        var stillOpen = await _detector.DetectAsync(m.Target, afterEsc, ct);
                        if (stillOpen.Found)
                        {
                            goneFrames = 0;
                            continue;
                        }

                        if (++goneFrames >= 2)
                        {
                            Log?.Invoke($"[monitor] {m.Target} ESC 후 닫힘 2프레임 확인 -> 원래 진행 계속");
                            return true;
                        }
                    }

                    throw new InvalidOperationException(
                        $"회복 물약 팝업 ESC 1회 후 닫힘을 확인하지 못했습니다. 구매 버튼은 누르지 않고 추가 입력 없이 정지합니다. target={m.Target}");
                }
''' + anchor

if anchor not in engine:
    raise SystemExit("ScenarioEngine monitor click anchor missing")
engine = engine.replace(anchor, escape_case, 1)
write(engine_path, engine)

# Reuse the proven popup-close detector/template for normal dungeon as well.
abyss_targets_path = app / "abyss" / "config" / "targets.json"
normal_targets_path = app / "dungeon" / "config" / "targets.json"
abyss_targets = load_json(abyss_targets_path)
normal_targets = load_json(normal_targets_path)

source_popup = next((t for t in abyss_targets if t.get("Id") == "abyss_popup_close"), None)
if source_popup is None:
    raise SystemExit("V0.1.59 abyss_popup_close target missing")

normal_targets = [t for t in normal_targets if t.get("Id") != "potion_popup_close"]
normal_popup = dict(source_popup)
normal_popup["Id"] = "potion_popup_close"
normal_targets.append(normal_popup)
save_json(normal_targets_path, normal_targets)

src_template = app / "abyss" / "templates" / "popup_close.png"
dst_template = app / "dungeon" / "templates" / "popup_close.png"
if not src_template.exists():
    raise SystemExit("V0.1.59 popup_close.png missing")
dst_template.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src_template, dst_template)

# Change Abyss popup from mouse click to keyboard ESC.
abyss_scenario_path = app / "abyss" / "config" / "scenario.json"
abyss_scenario = load_json(abyss_scenario_path)
abyss_popup_monitor = next((m for m in abyss_scenario.get("Monitors", [])
                            if m.get("Target") == "abyss_popup_close"), None)
if abyss_popup_monitor is None:
    raise SystemExit("V0.1.59 abyss popup monitor missing")
abyss_popup_monitor["Action"] = "escape"
save_json(abyss_scenario_path, abyss_scenario)

# Add the same behavior to the active normal-dungeon configuration.
normal_scenario_path = app / "dungeon" / "config" / "scenario.json"
normal_scenario = load_json(normal_scenario_path)
normal_monitors = [m for m in normal_scenario.get("Monitors", [])
                   if m.get("Target") != "potion_popup_close"]
normal_monitors.insert(0, {
    "Target": "potion_popup_close",
    "Action": "escape",
    "CooldownMs": 3000,
    "ScanIntervalMs": 1000
})
normal_scenario["Monitors"] = normal_monitors
save_json(normal_scenario_path, normal_scenario)

# ---------------------------------------------------------------------------
# 2) V0.1.60 Abyss result confirmation.
#    OCR of "다시 하기" is only a supporting signal now. A result is accepted
#    only when the visual result row independently confirms all three green
#    button regions. RetryAbyssResultAsync still requires two consecutive
#    accepted frames before any click.
# ---------------------------------------------------------------------------
retry_path = app / "dungeon" / "ScenarioEngine.AbyssRetry.cs"
retry = read(retry_path)

start_marker = "    private async Task<DetectionResult> DetectAbyssResultRetryAsync(Bitmap frame, CancellationToken ct)\n"
end_marker = "    private async Task RetryAbyssResultAsync(CancellationToken ct)\n"
start = retry.find(start_marker)
end = retry.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Abyss result detector method markers missing")

new_detector = '''    private async Task<DetectionResult> DetectAbyssResultRetryAsync(Bitmap frame, CancellationToken ct)
    {
        if (!IsAbyss) return DetectionResult.NotFound;

        double aspect = frame.Height == 0 ? 0 : frame.Width / (double)frame.Height;
        if (aspect < 0.74 || aspect > 0.86)
        {
            _lastAbyssResultDiagnostic = $"frame={frame.Width}x{frame.Height} aspect={aspect:0.000} outside-safe-range";
            return DetectionResult.NotFound;
        }

        // V0160_ABYSS_RESULT_MULTI_SIGNAL
        // Signal A: exact retry OCR inside the fixed safe ROI.
        _abyssResultOcr ??= new OcrRecognizer();
        var safeRetry = ScaleAbyssResultRoi(AbyssRetrySafeRoi, frame.Size);
        var retryOcr = await _abyssResultOcr.FindCompactLabelAsync(frame, safeRetry, "다시 하기", ct);
        bool ocrSignal = retryOcr.Found && safeRetry.Contains(retryOcr.Center);
        DiagnosticObserveDetection("abyss_result_retry_ocr", retryOcr);

        // Signal B/C/D: the production visual-row detector requires all three
        // canonical green result-button regions (exit/retry/other). OCR alone
        // is deliberately not authority for ResultConfirmed.
        bool visualSignal = TryDetectAbyssResultButtonRow(frame, out var visualRetry);
        if (!visualSignal)
        {
            _lastAbyssResultDiagnostic =
                $"frame={frame.Width}x{frame.Height} result-multisignal rejected " +
                $"ocr={(ocrSignal ? 1 : 0)} visualRow=0; {_lastAbyssResultDiagnostic}";
            DiagnosticObserveDetection("abyss_result_visual_row", DetectionResult.NotFound);
            return DetectionResult.NotFound;
        }

        var acceptedBounds = visualRetry;
        string source = ocrSignal
            ? "ocr+visual_result_button_row"
            : "visual_result_button_row_3signal";

        // If OCR also agrees, retain its exact text bounds only when its center
        // is inside the independently confirmed retry-button region.
        if (ocrSignal && visualRetry.Contains(retryOcr.Center))
            acceptedBounds = retryOcr.Bounds;

        var accepted = new DetectionResult(true, acceptedBounds, 0.95, source);
        _lastAbyssResultDiagnostic =
            $"frame={frame.Width}x{frame.Height} result-multisignal accepted " +
            $"ocr={(ocrSignal ? 1 : 0)} visualRow=1 retry={acceptedBounds}";
        DiagnosticObserveDetection("abyss_result_visual_row", accepted);
        return accepted;
    }

'''

retry = retry[:start] + new_detector + retry[end:]
write(retry_path, retry)

# ---------------------------------------------------------------------------
# 3) Version metadata.
# ---------------------------------------------------------------------------
project = app / "FishingAutomation.csproj"
project_text = read(project)
for old, new in (
    ("<Version>0.1.59</Version>", "<Version>0.1.60</Version>"),
    ("<AssemblyVersion>0.1.59.0</AssemblyVersion>", "<AssemblyVersion>0.1.60.0</AssemblyVersion>"),
    ("<FileVersion>0.1.59.0</FileVersion>", "<FileVersion>0.1.60.0</FileVersion>"),
):
    if old not in project_text:
        raise SystemExit(f"project version marker missing: {old}")
    project_text = project_text.replace(old, new, 1)
write(project, project_text)

update_path = app / "UpdateManager.cs"
update = read(update_path)
if 'CurrentVersion = "V0.1.59"' not in update:
    raise SystemExit("UpdateManager V0.1.59 marker missing")
update = update.replace('CurrentVersion = "V0.1.59"', 'CurrentVersion = "V0.1.60"', 1)
write(update_path, update)

# ---------------------------------------------------------------------------
# 4) Static safety invariants.
# ---------------------------------------------------------------------------
engine = read(engine_path)
retry = read(retry_path)
abyss_scenario = load_json(abyss_scenario_path)
normal_scenario = load_json(normal_scenario_path)
normal_targets = load_json(normal_targets_path)

required_engine = (
    'case "escape":',
    'POTION_POPUP_ESC_V1',
    '_input.TapScanCode(0x01);',
    'ESC 1회로 닫기 (구매 버튼 클릭 금지)',
    'ESC 후 닫힘 2프레임 확인',
)
for marker in required_engine:
    if marker not in engine:
        raise SystemExit(f"popup ESC safety marker missing: {marker}")

for scenario, target_id, label in (
    (abyss_scenario, "abyss_popup_close", "abyss"),
    (normal_scenario, "potion_popup_close", "dungeon"),
):
    monitors = [m for m in scenario.get("Monitors", []) if m.get("Target") == target_id]
    if len(monitors) != 1 or monitors[0].get("Action") != "escape":
        raise SystemExit(f"{label} popup monitor is not exactly one ESC monitor")

if not any(t.get("Id") == "potion_popup_close" for t in normal_targets):
    raise SystemExit("normal dungeon potion popup target missing")
if not dst_template.exists():
    raise SystemExit("normal dungeon popup_close.png copy missing")

for marker in (
    'V0160_ABYSS_RESULT_MULTI_SIGNAL',
    'bool ocrSignal',
    'bool visualSignal = TryDetectAbyssResultButtonRow',
    'result-multisignal rejected',
    'visual_result_button_row_3signal',
    'exitGreen < 0.18 || retryGreen < 0.18 || otherGreen < 0.18',
    'retry.Found && previous.Found && retry.Bounds.IntersectsWith(previous.Bounds)',
    'AbyssRequireState(AbyssFlowState.ResultConfirmed, "다시 하기 클릭")',
):
    if marker not in retry:
        raise SystemExit(f"V0.1.60 result safety marker missing: {marker}")

# OCR-only acceptance from V0.1.59 must be gone.
ocr_block_start = retry.find('var retryOcr = await _abyssResultOcr.FindCompactLabelAsync')
visual_block_start = retry.find('bool visualSignal = TryDetectAbyssResultButtonRow', ocr_block_start)
if ocr_block_start < 0 or visual_block_start < 0:
    raise SystemExit("V0.1.60 OCR/visual ordering missing")
if 'return retryOcr;' in retry[ocr_block_start:visual_block_start]:
    raise SystemExit("OCR-only result acceptance still present")

if "<Version>0.1.60</Version>" not in read(project):
    raise SystemExit("project version not V0.1.60")
if 'CurrentVersion = "V0.1.60"' not in read(update_path):
    raise SystemExit("UpdateManager version not V0.1.60")

print("V0.1.60 applied: potion popup ESC close + Abyss multi-signal result confirmation")
