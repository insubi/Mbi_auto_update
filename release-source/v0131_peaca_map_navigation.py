#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0131_peaca_map_navigation.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
main_path = app / "MainForm.cs"
dash_path = app / "MainForm.Dashboard.cs"
ref_path = app / "MainForm.ReferenceUI.cs"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
input_path = app / "dungeon" / "InputController.cs"
targets_path = app / "dungeon" / "config" / "targets.json"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label} anchor not found")
    return text.replace(old, new, 1)


def upsert(items, target):
    for i, old in enumerate(items):
        if str(old.get("Id", "")).lower() == str(target["Id"]).lower():
            items[i] = target
            return
    items.append(target)


# -----------------------------------------------------------------------------
# 1) OCR targets used only by the Peaca travel preparation flow.
# -----------------------------------------------------------------------------
targets = json.loads(read(targets_path))
peaca_targets = [
    {
        "Id": "map_ula_header",
        "Kind": "ocr",
        "Roi": {"X": 0, "Y": 0, "Width": 300, "Height": 120},
        "Text": "울라 대륙",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "peaca_map_name",
        "Kind": "ocr",
        "Roi": {"X": 0, "Y": 80, "Width": 620, "Height": 720},
        "Text": "페카 고분",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "peaca_detail_name",
        "Kind": "ocr",
        "Roi": {"X": 100, "Y": 500, "Width": 600, "Height": 320},
        "Text": "페카 고분",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "peaca_goto",
        "Kind": "ocr",
        "Roi": {"X": 100, "Y": 760, "Width": 600, "Height": 240},
        "Text": "여기로 가기",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "peaca_deep_tab",
        "Kind": "ocr",
        "Roi": {"X": 0, "Y": 60, "Width": 360, "Height": 180},
        "Text": "심층 던전",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "peaca_deep_screen",
        "Kind": "ocr",
        "Roi": {"X": 80, "Y": 330, "Width": 620, "Height": 430},
        "Text": "심층 1층",
        "MaxEditDistance": 1,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "peaca_entry_11",
        "Kind": "ocr",
        "Roi": {"X": 100, "Y": 850, "Width": 600, "Height": 150},
        "Text": "심층 1층 1구역 진입",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    },
    {
        "Id": "peaca_entry_22",
        "Kind": "ocr",
        "Roi": {"X": 100, "Y": 850, "Width": 600, "Height": 150},
        "Text": "심층 2층 2구역 진입",
        "MaxEditDistance": 2,
        "OcrRetryAt2x": True,
    },
]
for t in peaca_targets:
    upsert(targets, t)
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")


# -----------------------------------------------------------------------------
# 2) Add a verified Interception drag primitive for deterministic map panning.
# -----------------------------------------------------------------------------
input_cs = read(input_path)
input_cs = replace_once(
    input_cs,
    """    void ClickClientPoint(nint hwnd, Point clientPoint);\n    void TapScanCode(ushort scanCode);\n""",
    """    void ClickClientPoint(nint hwnd, Point clientPoint);\n    void DragClientPoint(nint hwnd, Point from, Point to, int durationMs);\n    void TapScanCode(ushort scanCode);\n""",
    "input interface",
)

click_end = """        Thread.Sleep(30);\n    }\n\n    public void TapScanCode(ushort scanCode)\n"""
drag_impl = """        Thread.Sleep(30);\n    }\n\n    public void DragClientPoint(nint hwnd, Point from, Point to, int durationMs)\n    {\n        if (hwnd == 0)\n            throw new InvalidOperationException(\"게임 창 핸들이 없습니다.\");\n\n        var origin = new NativeMethods.POINT { X = 0, Y = 0 };\n        if (!NativeMethods.ClientToScreen(hwnd, ref origin))\n            throw new InvalidOperationException(\"게임 창 좌표를 화면 좌표로 변환하지 못했습니다.\");\n\n        int sx0 = origin.X + from.X;\n        int sy0 = origin.Y + from.Y;\n        int sx1 = origin.X + to.X;\n        int sy1 = origin.Y + to.Y;\n\n        NativeMethods.SetForegroundWindow(hwnd);\n        Thread.Sleep(100);\n        SendAbsolute(_mouseDevice, sx0, sy0);\n        Thread.Sleep(80);\n\n        SendMouse(_mouseDevice, new InterceptionMouseStroke { state = MOUSE_LEFT_DOWN });\n        Thread.Sleep(70);\n        try\n        {\n            int totalMs = Math.Clamp(durationMs, 350, 1600);\n            int steps = Math.Clamp(totalMs / 45, 10, 32);\n            int sleep = Math.Max(12, totalMs / steps);\n            for (int i = 1; i <= steps; i++)\n            {\n                double t = (double)i / steps;\n                // Smoothstep avoids a sudden jump that can be interpreted as a click.\n                t = t * t * (3.0 - 2.0 * t);\n                int sx = (int)Math.Round(sx0 + (sx1 - sx0) * t);\n                int sy = (int)Math.Round(sy0 + (sy1 - sy0) * t);\n                SendAbsolute(_mouseDevice, sx, sy);\n                Thread.Sleep(sleep);\n            }\n        }\n        finally\n        {\n            SendMouse(_mouseDevice, new InterceptionMouseStroke { state = MOUSE_LEFT_UP });\n        }\n\n        Thread.Sleep(100);\n        if (!GetCursorPos(out var actual) || Math.Abs(actual.X - sx1) > 8 || Math.Abs(actual.Y - sy1) > 8)\n            throw new InvalidOperationException($\"지도 드래그 후 실제 커서가 목표 위치에 도달하지 않았습니다. target=({sx1},{sy1}) cursor=({actual.X},{actual.Y})\");\n    }\n\n    public void TapScanCode(ushort scanCode)\n"""
input_cs = replace_once(input_cs, click_end, drag_impl, "drag implementation")
write(input_path, input_cs)


# -----------------------------------------------------------------------------
# 3) ScenarioEngine: Peaca map navigation is a pre-flight preparation only.
#    Existing dungeon RunAsync remains untouched and receives control after challenge
#    screen is visible.
# -----------------------------------------------------------------------------
engine = read(engine_path)
run_anchor = "    public async Task RunAsync(CancellationToken ct)\n"
if run_anchor not in engine:
    raise RuntimeError("ScenarioEngine RunAsync anchor missing")

peaca_engine = r'''    // PEACA_MAP_NAVIGATION_V1
    public async Task PreparePeacaDeepDungeonAsync(string stage, CancellationToken ct)
    {
        if (stage != "1-1" && stage != "2-2")
            throw new ArgumentOutOfRangeException(nameof(stage), stage, "지원하는 페카 심층 구역은 1-1 / 2-2 입니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[페카 이동] 시작 -> 심층 {stage}");

        // M: open the map. Never continue until the Ula breadcrumb is actually visible.
        _input.TapScanCode(0x32);
        var ula = await WaitForPeacaTargetAsync("map_ula_header", TimeSpan.FromSeconds(10), ct);
        Log?.Invoke($"[페카 이동] 지도 열림 확인: {ula.ReadText}");

        // The Ula continent breadcrumb is fixed in the upper-left of the 800x1000 client.
        _input.ClickClientPoint(_hwnd, new Point(95, 45));
        await Task.Delay(1100, ct);
        Log?.Invoke("[페카 이동] 울라 대륙 클릭 완료 -> 월드맵 좌상단 기준점 정렬");

        await AlignPeacaMapTopLeftAsync(ct);
        var peaca = await FindPeacaOnWorldMapAsync(ct);
        Log?.Invoke($"[페카 이동] 페카 고분 OCR 발견 @ {peaca.Bounds}");

        // Click only the OCR-derived Peaca location. No guessed fallback coordinate.
        _input.ClickClientPoint(_hwnd, peaca.Center);
        bool selected = await VerifyPeacaWorldSelectionAsync(ct);
        if (!selected)
            throw new TimeoutException("페카 고분을 클릭했지만 '페카 고분 + 여기로 가기' 화면을 확인하지 못했습니다.");

        Log?.Invoke("[페카 이동] 페카 고분 + 여기로 가기 확인 -> Space");
        NativeMethods.SetForegroundWindow(_hwnd);
        _input.TapScanCode(0x39);

        // Travel/loading may take time. The deep-dungeon tab is our arrival proof.
        var deepTab = await WaitForPeacaTargetAsync("peaca_deep_tab", TimeSpan.FromSeconds(60), ct);
        Log?.Invoke($"[페카 이동] 페카 고분 도착 확인 -> 심층 던전 탭 클릭 @ {deepTab.Bounds}");
        _input.ClickClientPoint(_hwnd, deepTab.Center);

        await WaitForPeacaTargetAsync("peaca_deep_screen", TimeSpan.FromSeconds(12), ct);
        Point stagePoint = stage == "1-1" ? new Point(315, 525) : new Point(398, 830);
        Log?.Invoke($"[페카 이동] 심층 {stage} 고정 슬롯 클릭 @ {stagePoint}");
        _input.ClickClientPoint(_hwnd, stagePoint);
        await Task.Delay(650, ct);

        string entryTarget = stage == "1-1" ? "peaca_entry_11" : "peaca_entry_22";
        var entry = await WaitForPeacaTargetAsync(entryTarget, TimeSpan.FromSeconds(8), ct);
        Log?.Invoke($"[페카 이동] 진입 문구 확인: {entry.ReadText} -> Space");
        NativeMethods.SetForegroundWindow(_hwnd);
        _input.TapScanCode(0x39);

        // Handoff only after the existing macro's first selected/challenge screen is visible.
        var handoff = Stopwatch.StartNew();
        while (handoff.Elapsed < TimeSpan.FromSeconds(18))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var selectedState = await _detector.DetectAsync("selected", frame, ct);
            if (selectedState.Found)
            {
                Log?.Invoke("[페카 이동] 선택됨 화면 확인 -> 기존 던전 매크로로 인계");
                return;
            }

            var challengeState = await _detector.DetectAsync("challenge", frame, ct);
            if (challengeState.Found)
            {
                Log?.Invoke("[페카 이동] 도전 화면 확인 -> 기존 던전 매크로로 인계");
                return;
            }
            await Task.Delay(400, ct);
        }

        throw new TimeoutException("페카 심층 구역 진입 후 기존 던전 매크로의 선택됨/도전 화면을 확인하지 못했습니다.");
    }

    private async Task<DetectionResult> WaitForPeacaTargetAsync(string targetId, TimeSpan timeout, CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        while (sw.Elapsed < timeout)
        {
            ct.ThrowIfCancellationRequested();
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            using var frame = await CaptureGameWindowAsync(ct);
            var found = await _detector.DetectAsync(targetId, frame, ct);
            if (found.Found)
                return found;
            await Task.Delay(350, ct);
        }
        throw new TimeoutException($"페카 자동이동 화면 확인 실패: {targetId} ({timeout.TotalSeconds:0}초)");
    }

    private async Task AlignPeacaMapTopLeftAsync(CancellationToken ct)
    {
        const double stationaryThreshold = 7.0;
        int stationary = 0;
        for (int attempt = 1; attempt <= 14; attempt++)
        {
            ct.ThrowIfCancellationRequested();
            using var before = await CaptureGameWindowAsync(ct);
            _input.DragClientPoint(_hwnd, new Point(260, 300), new Point(570, 680), 850);
            await Task.Delay(320, ct);
            using var after = await CaptureGameWindowAsync(ct);
            double diff = PeacaMapFrameDifference(before, after);
            stationary = diff < stationaryThreshold ? stationary + 1 : 0;
            Log?.Invoke($"[페카 이동] 좌상단 정렬 {attempt}/14 diff={diff:0.00}, 경계확인={stationary}/2");
            if (stationary >= 2)
            {
                Log?.Invoke("[페카 이동] 화면 변화 거의 없음 2회 -> 월드맵 좌상단 경계 확정");
                return;
            }
        }
        throw new TimeoutException("울라 월드맵을 좌상단 경계까지 정렬하지 못했습니다.");
    }

    private async Task<DetectionResult> FindPeacaOnWorldMapAsync(CancellationToken ct)
    {
        const double stationaryThreshold = 7.0;
        bool scanRight = true;

        // Bounded serpentine scan: at most 5 rows x 7 horizontal viewports.
        for (int row = 0; row < 5; row++)
        {
            int horizontalEdge = 0;
            for (int col = 0; col < 7; col++)
            {
                ct.ThrowIfCancellationRequested();
                using (var frame = await CaptureGameWindowAsync(ct))
                {
                    var found = await _detector.DetectAsync("peaca_map_name", frame, ct);
                    if (found.Found)
                    {
                        Log?.Invoke($"[페카 이동] 지도 탐색 row={row + 1}, col={col + 1} -> 페카 고분 발견");
                        return found;
                    }
                }

                if (col == 6) break;
                using var before = await CaptureGameWindowAsync(ct);
                Point from = scanRight ? new Point(560, 450) : new Point(190, 450);
                Point to = scanRight ? new Point(190, 450) : new Point(560, 450);
                _input.DragClientPoint(_hwnd, from, to, 820);
                await Task.Delay(300, ct);
                using var after = await CaptureGameWindowAsync(ct);
                double diff = PeacaMapFrameDifference(before, after);
                horizontalEdge = diff < stationaryThreshold ? horizontalEdge + 1 : 0;
                Log?.Invoke($"[페카 이동] {(scanRight ? "오른쪽" : "왼쪽")} 탐색 이동 diff={diff:0.00}, 경계확인={horizontalEdge}/2");
                if (horizontalEdge >= 2)
                    break;
            }

            if (row == 4) break;

            // One row down = drag map content upward. If it is already at the bottom,
            // require two low-change attempts before terminating the bounded search.
            int bottomEdge = 0;
            bool movedDown = false;
            for (int check = 0; check < 2; check++)
            {
                using var before = await CaptureGameWindowAsync(ct);
                _input.DragClientPoint(_hwnd, new Point(380, 660), new Point(380, 300), 820);
                await Task.Delay(300, ct);
                using var after = await CaptureGameWindowAsync(ct);
                double diff = PeacaMapFrameDifference(before, after);
                if (diff < stationaryThreshold)
                {
                    bottomEdge++;
                    Log?.Invoke($"[페카 이동] 아래쪽 이동 diff={diff:0.00}, 하단 경계확인={bottomEdge}/2");
                }
                else
                {
                    movedDown = true;
                    Log?.Invoke($"[페카 이동] 다음 탐색 행으로 이동 diff={diff:0.00}");
                    break;
                }
            }
            if (!movedDown && bottomEdge >= 2)
                break;

            scanRight = !scanRight;
        }

        throw new TimeoutException("울라 월드맵 지그재그 탐색 범위에서 '페카 고분'을 찾지 못했습니다. 임의 좌표는 클릭하지 않습니다.");
    }

    private async Task<bool> VerifyPeacaWorldSelectionAsync(CancellationToken ct)
    {
        var sw = Stopwatch.StartNew();
        while (sw.Elapsed < TimeSpan.FromSeconds(6))
        {
            ct.ThrowIfCancellationRequested();
            using var frame = await CaptureGameWindowAsync(ct);
            var name = await _detector.DetectAsync("peaca_detail_name", frame, ct);
            var go = await _detector.DetectAsync("peaca_goto", frame, ct);
            if (name.Found && go.Found)
                return true;
            await Task.Delay(350, ct);
        }
        return false;
    }

    private static double PeacaMapFrameDifference(Bitmap a, Bitmap b)
    {
        // Compare only the map body. Right quest overlay and bottom navigation are excluded.
        int width = Math.Min(a.Width, b.Width);
        int height = Math.Min(a.Height, b.Height);
        var roi = Rectangle.Intersect(new Rectangle(70, 130, 500, 540), new Rectangle(0, 0, width, height));
        if (roi.Width < 20 || roi.Height < 20) return double.MaxValue;

        long total = 0;
        int count = 0;
        const int step = 12;
        for (int y = roi.Top; y < roi.Bottom; y += step)
        {
            for (int x = roi.Left; x < roi.Right; x += step)
            {
                Color ca = a.GetPixel(x, y);
                Color cb = b.GetPixel(x, y);
                total += Math.Abs(ca.R - cb.R) + Math.Abs(ca.G - cb.G) + Math.Abs(ca.B - cb.B);
                count += 3;
            }
        }
        return count == 0 ? double.MaxValue : (double)total / count;
    }

'''
engine = engine.replace(run_anchor, peaca_engine + run_anchor, 1)
write(engine_path, engine)


# -----------------------------------------------------------------------------
# 4) UI: the existing "선택 던전" menu also serves regular dungeon destinations.
#    Default "현재 위치" preserves the V0.1.30 manual-start behavior exactly.
# -----------------------------------------------------------------------------
main = read(main_path)
main = replace_once(
    main,
    "    private readonly ComboBox _abyssDungeon = new();\n",
    "    private readonly ComboBox _abyssDungeon = new();\n    private readonly ComboBox _dungeonDestination = new();\n",
    "dungeon destination field",
)

abyss_event = '''        _abyssDungeon.SelectedIndexChanged += (_, _) =>
        {
            if (_activeMode is null && SelectedMode == "어비스")
            {
                _log.Write($"[어비스] 선택 던전: {SelectedAbyssDungeon}");
                RefreshModeStatus();
            }
        };
'''
dungeon_event = '''        _dungeonDestination.SelectedIndexChanged += (_, _) =>
        {
            if (_activeMode is null && SelectedMode == "던전")
            {
                _log.Write($"[던전] 선택 던전: {SelectedDungeonDestination}");
                RefreshModeStatus();
                UpdateStats();
            }
        };

'''
main = replace_once(main, abyss_event, dungeon_event + abyss_event, "dungeon destination event")
main = replace_once(
    main,
    '    private string SelectedMode => _mode.SelectedItem?.ToString() ?? "낚시";\n',
    '    private string SelectedMode => _mode.SelectedItem?.ToString() ?? "낚시";\n    private string SelectedDungeonDestination => _dungeonDestination.SelectedItem?.ToString() ?? "현재 위치";\n',
    "dungeon destination property",
)

engine_create = "            var engine = new ScenarioEngine(window.Handle, settings, scenario, targets, baseDir);\n"
engine_create_new = '''            string? peacaStage = modeName == "던전" ? SelectedDungeonDestination switch
            {
                "페카 심층 1-1" => "1-1",
                "페카 심층 2-2" => "2-2",
                _ => null
            } : null;
            var engine = new ScenarioEngine(window.Handle, settings, scenario, targets, baseDir);
'''
main = replace_once(main, engine_create, engine_create_new, "capture Peaca stage")
main = replace_once(
    main,
    "                        await engine.RunAsync(_dungeonCts.Token);\n",
    '''                        if (peacaStage is not null)
                        {
                            Ui(() => SetStatus($"페카 심층 {peacaStage} 자동 이동 중", Blue));
                            await engine.PreparePeacaDeepDungeonAsync(peacaStage, _dungeonCts.Token);
                            Ui(() => SetStatus("던전 실행 중", Blue));
                        }
                        await engine.RunAsync(_dungeonCts.Token);
''',
    "Peaca preflight call",
)
write(main_path, main)

for ui_path in (dash_path, ref_path):
    ui = read(ui_path)
    ui = replace_once(
        ui,
        '        _mode.SelectedIndex = 0;\n',
        '        _mode.SelectedIndex = 0;\n        _dungeonDestination.Items.AddRange(new object[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-2" });\n        _dungeonDestination.SelectedIndex = 0;\n',
        f"dungeon destination items in {ui_path.name}",
    )
    write(ui_path, ui)

ref = read(ref_path)
old_select = '''        private void SelectDungeon(int index)
        {
            _owner.SafeUiAction("어비스 던전 선택", () =>
            {
                if (_owner.AnyRunning || _owner._activeMode is not null) return;
                if (index < 0 || index >= _owner._abyssDungeon.Items.Count) return;
                _owner._mode.SelectedIndex = 2;
                _owner._abyssDungeon.SelectedIndex = index;
                _owner.UpdateDashboard();
            });
        }
'''
new_select = '''        private void SelectDungeon(int index)
        {
            _owner.SafeUiAction("던전 선택", () =>
            {
                if (_owner.AnyRunning || _owner._activeMode is not null) return;
                string mode = _owner._mode.SelectedItem?.ToString() ?? "";
                if (mode == "던전")
                {
                    if (index < 0 || index >= _owner._dungeonDestination.Items.Count) return;
                    _owner._dungeonDestination.SelectedIndex = index;
                }
                else if (mode == "어비스")
                {
                    if (index < 0 || index >= _owner._abyssDungeon.Items.Count) return;
                    _owner._abyssDungeon.SelectedIndex = index;
                }
                else return;
                _owner.UpdateDashboard();
            });
        }
'''
ref = replace_once(ref, old_select, new_select, "reference SelectDungeon")
old_show = '''        private void ShowDungeonMenu()
        {
            if (_owner.AnyRunning || _owner._activeMode is not null) return;

            // 허상의 정박지 / 광기의 동굴 / 흩어진 물길은 모두 어비스 전용이다.
            // 현재 모드가 낚시 또는 던전이면 선택 던전 버튼을 눌러도
            // 아무 메뉴도 표시하지 않는다. 왼쪽 낚시/던전 버튼으로
            // 모드를 바꾼 경우에도 동일하게 적용된다.
            if (!string.Equals(_owner._mode.SelectedItem?.ToString(), "어비스", StringComparison.Ordinal))
                return;

            ShowMenu(new[] { "허상의 정박지", "광기의 동굴", "흩어진 물길" }, SelectDungeon, 680, 312);
        }
'''
new_show = '''        private void ShowDungeonMenu()
        {
            if (_owner.AnyRunning || _owner._activeMode is not null) return;
            string mode = _owner._mode.SelectedItem?.ToString() ?? "";
            if (mode == "던전")
            {
                ShowMenu(new[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-2" }, SelectDungeon, 680, 312);
                return;
            }
            if (mode == "어비스")
                ShowMenu(new[] { "허상의 정박지", "광기의 동굴", "흩어진 물길" }, SelectDungeon, 680, 312);
        }
'''
ref = replace_once(ref, old_show, new_show, "reference ShowDungeonMenu")
write(ref_path, ref)

# Dashboard selected-dungeon card now reflects regular dungeon destination too.
dash = read(dash_path)
dash = replace_once(
    dash,
    '        bool abyss = (_activeMode ?? SelectedMode) == "어비스";\n',
    '        bool abyss = (_activeMode ?? SelectedMode) == "어비스";\n        bool dungeon = (_activeMode ?? SelectedMode) == "던전";\n',
    "dashboard mode flags",
)
dash = replace_once(
    dash,
    '        _currentDungeonValue.Text = abyss ? SelectedAbyssDungeon : "—";\n',
    '        _currentDungeonValue.Text = abyss ? SelectedAbyssDungeon : dungeon ? SelectedDungeonDestination : "—";\n',
    "dashboard current dungeon",
)
dash = replace_once(
    dash,
    '        _miniInfo.Text = $"{(abyss ? SelectedAbyssDungeon : _activeMode ?? SelectedMode)} · {_stageTime.Text}";\n',
    '        _miniInfo.Text = $"{(abyss ? SelectedAbyssDungeon : dungeon ? SelectedDungeonDestination : _activeMode ?? SelectedMode)} · {_stageTime.Text}";\n',
    "dashboard mini dungeon",
)
write(dash_path, dash)


# -----------------------------------------------------------------------------
# 5) Version bump and change log. Do not alter image/template file names.
# -----------------------------------------------------------------------------
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.30", "V0.1.31")
                   .replace("0.1.30.0", "0.1.31.0")
                   .replace("0.1.30", "0.1.31"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.31_PEACA_MAP_NAVIGATION.txt").write_text(
    "MABI AUTO V0.1.31 - PEACA MAP NAVIGATION TEST\n\n"
    "Base: V0.1.30 without policy/ERROR88 OCR detection.\n"
    "Regular Dungeon '선택 던전' now offers 현재 위치, 페카 심층 1-1, 페카 심층 2-2.\n"
    "Peaca selections run a bounded pre-flight: M -> 울라 대륙 -> top-left boundary detection -> serpentine OCR search for 페카 고분 -> verified 여기로 가기 -> 심층 던전 -> selected stage -> existing selected/challenge macro handoff.\n"
    "Map edge detection requires two consecutive low-change frames and never clicks a guessed POI when OCR fails.\n"
    "Current-position selection preserves the existing V0.1.30 manual dungeon start behavior.\n"
    "V0.1.30 policy/ERROR88 removal, V0.1.29 retry hybrid + recovery cap + two-frame scene skip, existing Abyss/Fishing/F10/Telegram are preserved.\n",
    encoding="utf-8"
)

print("V0.1.31 applied: Peaca map navigation + regular dungeon selection menu")
