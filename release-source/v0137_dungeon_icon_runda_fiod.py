#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0137_dungeon_icon_runda_fiod.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
main_path = app / "MainForm.cs"
refui_path = app / "MainForm.ReferenceUI.cs"
engine_path = app / "dungeon" / "ScenarioEngine.cs"
targets_path = app / "dungeon" / "config" / "targets.json"
updater_path = root / "tools" / "ApplyUpdate.ps1"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

# 1) Dungeon destination list / pre-route mapping.
main = read(main_path)
main = replace_once(
    main,
    '''    private string? SelectedDungeonPreRoute => SelectedDungeonDestination switch
    {
        "페카 심층 1-1" => "peaca_d1_1",
        "페카 심층 2-1" => "peaca_d2_1",
        _ => null
    };
''',
    '''    private string? SelectedDungeonPreRoute => SelectedDungeonDestination switch
    {
        "페카 심층 1-1" => "peaca_d1_1",
        "페카 심층 2-1" => "peaca_d2_1",
        "룬다 1-1" => "runda_d1_1",
        "룬다 2-1" => "runda_d2_1",
        "피오드 1-1" => "fiod_d1_1",
        "피오드 2-1" => "fiod_d2_1",
        _ => null
    };
''',
    "dungeon pre-route mapping")
write(main_path, main)

refui = read(refui_path)
refui = replace_once(
    refui,
    '_dungeonDestination.Items.AddRange(new object[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-1" });',
    '_dungeonDestination.Items.AddRange(new object[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-1", "룬다 1-1", "룬다 2-1", "피오드 1-1", "피오드 2-1" });',
    "regular dungeon combo items")
refui = replace_once(
    refui,
    'ShowMenu(new[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-1" }, SelectRegularDungeon, 680, 312);',
    'ShowMenu(new[] { "현재 위치", "페카 심층 1-1", "페카 심층 2-1", "룬다 1-1", "룬다 2-1", "피오드 1-1", "피오드 2-1" }, SelectRegularDungeon, 680, 312);',
    "regular dungeon popup items")

# UI hotfix: the unknown 'test' icon consumed the text area and made '인식 테스트' ellipsize.
refui = replace_once(
    refui,
    'AddButton("인식 테스트", new(18, 511, 170, 59), owner.ShowVisualRecognitionTest, "test", "nav");',
    'AddButton("인식 테스트", new(18, 511, 178, 59), owner.ShowVisualRecognitionTest, "", "nav");',
    "visual test sidebar text")
write(refui_path, refui)

# 2) Generalize the Peaca-only pre-route to Peaca/Runda/Fiod.
engine = read(engine_path)
engine = replace_once(
    engine,
    '            await RunPeacaPreRouteAsync(_preRoute!, ct);',
    '            await RunDungeonPreRouteAsync(_preRoute!, ct);',
    "pre-route call")

start_marker = '    // PEACA_AUTO_ROUTE_V1\n    private async Task RunPeacaPreRouteAsync'
end_marker = '    private async Task<DetectionResult> WaitForTargetAsync'
start = engine.find(start_marker)
end = engine.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("pre-route method range not found")

new_method = r'''    // DUNGEON_WORLD_ROUTE_V11
    private async Task RunDungeonPreRouteAsync(string route, CancellationToken ct)
    {
        bool isPeaca = route.StartsWith("peaca_", StringComparison.OrdinalIgnoreCase);
        bool isRunda = route.StartsWith("runda_", StringComparison.OrdinalIgnoreCase);
        bool isFiod = route.StartsWith("fiod_", StringComparison.OrdinalIgnoreCase);
        bool d11 = route.EndsWith("d1_1", StringComparison.OrdinalIgnoreCase);
        bool d21 = route.EndsWith("d2_1", StringComparison.OrdinalIgnoreCase);
        if ((!isPeaca && !isRunda && !isFiod) || (!d11 && !d21))
            throw new InvalidOperationException($"지원하지 않는 던전 자동 이동 경로: {route}");

        string dungeonName = isPeaca ? "페카 고분" : isRunda ? "룬다 던전" : "피오드 던전";
        string destination = isPeaca
            ? (d11 ? "페카 심층 1-1" : "페카 심층 2-1")
            : $"{dungeonName.Replace(" 던전", "")} {(d11 ? "1-1" : "2-1")}";
        string mapTarget = isPeaca ? "route_peaca_map" : isRunda ? "route_runda_map" : "route_fiod_map";
        string popupTarget = isPeaca ? "route_peaca_popup_title" : isRunda ? "route_runda_popup_title" : "route_fiod_popup_title";
        string arrivalTarget = isPeaca ? "route_peaca_title" : isRunda ? "route_runda_title" : "route_fiod_title";

        Log?.Invoke($"[던전 자동이동] 시작 -> {destination}");
        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);

        using var beforeMapOpen = await CaptureGameWindowAsync(ct);
        Log?.Invoke("[던전 자동이동] M 입력 -> 지도 열기");
        _input.TapScanCode(0x32); // M
        await Task.Delay(1200, ct);

        using var localMapFrame = await CaptureGameWindowAsync(ct);
        double mapOpenDiff = MapFrameDifference(beforeMapOpen, localMapFrame);
        Log?.Invoke($"[던전 자동이동] M 입력 후 화면변화={mapOpenDiff:0.00}");
        if (mapOpenDiff <= 6.0)
            throw new TimeoutException("M 입력 후 지도 화면 전환을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        var ullaBreadcrumbPoint = new Point(82, 66);
        Log?.Invoke($"[던전 자동이동] 좌측 상단 울라 대륙 고정 위치 클릭 @ {ullaBreadcrumbPoint}");
        _input.ClickClientPoint(_hwnd, ullaBreadcrumbPoint);
        await Task.Delay(1200, ct);

        using var worldMapFrame = await CaptureGameWindowAsync(ct);
        double continentOpenDiff = MapFrameDifference(localMapFrame, worldMapFrame);
        Log?.Invoke($"[던전 자동이동] 울라 대륙 클릭 후 화면변화={continentOpenDiff:0.00}");
        if (continentOpenDiff <= 6.0)
            throw new TimeoutException("좌측 상단 울라 대륙 고정 위치 클릭 후 월드맵 전환을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        await AlignWorldMapTopLeftAsync(ct);
        var mapLabel = await FindDungeonOnWorldMapAsync(mapTarget, dungeonName, ct);
        if (!mapLabel.Found)
            throw new TimeoutException($"울라 대륙 지도를 제한 범위까지 탐색했지만 '{dungeonName}'을 찾지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        // The OCR label is ONLY an anchor. Never click the text itself.
        // Find the saturated purple/blue-highlight dungeon icon immediately above that label.
        using var iconFrame = await CaptureGameWindowAsync(ct);
        if (!TryFindDungeonIconAboveLabel(iconFrame, mapLabel.Bounds, out var iconBounds))
            throw new TimeoutException($"{dungeonName} 글씨는 찾았지만 위쪽 던전 아이콘을 확인하지 못했습니다. 글씨나 대체 좌표를 누르지 않고 정지합니다.");

        var iconCenter = new Point(iconBounds.Left + iconBounds.Width / 2, iconBounds.Top + iconBounds.Height / 2);
        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[던전 자동이동] {dungeonName} OCR 확인 -> 위 던전 아이콘 클릭 @ {iconBounds}");
        _input.ClickClientPoint(_hwnd, iconCenter);
        await Task.Delay(700, ct);

        bool popupReady = await WaitForTargetPairAsync(popupTarget, "route_go_here", 8, ct);
        if (!popupReady)
            throw new TimeoutException($"{dungeonName} 아이콘 클릭 후 '{dungeonName} + 여기로 가기' 확인에 실패했습니다. Space를 누르지 않습니다.");

        Log?.Invoke($"[던전 자동이동] {dungeonName} + 여기로 가기 확인 -> Space");
        _input.TapScanCode(0x39);
        await Task.Delay(800, ct);

        if (isPeaca)
        {
            bool arrived = await WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 30, ct);
            if (!arrived)
                throw new TimeoutException("이동 후 30초 안에 페카 고분 도착/심층 던전 탭을 확인하지 못했습니다.");

            DetectionResult deepTab;
            using (var arrivedFrame = await CaptureGameWindowAsync(ct))
                deepTab = await _detector.DetectAsync("route_deep_tab", arrivedFrame, ct);
            if (!deepTab.Found)
                throw new TimeoutException("페카 고분 도착 후 심층 던전 탭을 다시 확인하지 못했습니다.");

            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            Log?.Invoke($"[던전 자동이동] 심층 던전 탭 클릭 @ {deepTab.Bounds}");
            _input.ClickClientPoint(_hwnd, deepTab.Center);
            await Task.Delay(900, ct);
        }
        else
        {
            var arrived = await WaitForTargetAsync(arrivalTarget, 30, ct);
            if (!arrived.Found)
                throw new TimeoutException($"이동 후 30초 안에 {dungeonName} 도착 화면을 확인하지 못했습니다.");
            Log?.Invoke($"[던전 자동이동] {dungeonName} 도착 화면 확인");
        }

        string slotTarget = isPeaca
            ? (d11 ? "route_d1_1" : "route_d2_1")
            : (d11 ? "route_regular_1_1" : "route_regular_2_1");
        string enterTarget = isPeaca
            ? (d11 ? "route_enter_d1_1" : "route_enter_d2_1")
            : (d11 ? "route_enter_regular_1_1" : "route_enter_regular_2_1");

        var slot = await WaitForTargetAsync(slotTarget, 10, ct);
        if (!slot.Found)
            throw new TimeoutException($"{destination}의 {(d11 ? "1-1" : "2-1")} 표기를 10초 안에 찾지 못했습니다. 다른 구역을 대신 누르지 않습니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        Log?.Invoke($"[던전 자동이동] {destination} 구역 확인 -> 클릭 @ {slot.Bounds}");
        _input.ClickClientPoint(_hwnd, slot.Center);
        await Task.Delay(650, ct);

        var enter = await WaitForTargetAsync(enterTarget, 8, ct);
        if (!enter.Found)
            throw new TimeoutException($"{destination} 선택 후 정확한 진입 문구를 확인하지 못했습니다. Space를 누르지 않습니다.");

        Log?.Invoke($"[던전 자동이동] {destination} 진입 문구 확인 -> Space");
        _input.TapScanCode(0x39);

        var handoff = await WaitForTargetAsync("enter_bottom", 20, ct);
        if (!handoff.Found)
            throw new TimeoutException($"{destination} 진입 후 기존 던전 매크로 초입 '입장하기' 화면을 20초 안에 확인하지 못했습니다.");

        Log?.Invoke("[던전 자동이동] 기존 던전 매크로 초입 확인 완료 -> 기존 선택됨/도전/입장 로직으로 인계");
    }

'''
engine = engine[:start] + new_method + engine[end:]

# Generic map search, keeping the existing bounded serpentine behavior.
search_start_marker = '    private async Task<DetectionResult> FindPeacaOnWorldMapAsync'
search_end_marker = '    private static double MapFrameDifference'
ss = engine.find(search_start_marker)
se = engine.find(search_end_marker, ss)
if ss < 0 or se < 0:
    raise RuntimeError("world-map search method range not found")

generic_search = r'''    private async Task<DetectionResult> FindDungeonOnWorldMapAsync(
        string mapTarget,
        string dungeonName,
        CancellationToken ct)
    {
        const double EdgeThreshold = 6.0;
        bool moveViewportRight = true;
        Log?.Invoke($"[던전 자동이동] {dungeonName} · 좌상단 기준 지그재그 탐색 시작");

        for (int row = 0; row < 4; row++)
        {
            int edgeStable = 0;
            for (int col = 0; col < 6; col++)
            {
                ct.ThrowIfCancellationRequested();
                using var frame = await CaptureGameWindowAsync(ct);
                var found = await _detector.DetectAsync(mapTarget, frame, ct);
                if (found.Found)
                {
                    Log?.Invoke($"[던전 자동이동] {dungeonName} 글씨 발견 row={row + 1}, col={col + 1} @ {found.Bounds}");
                    return found;
                }

                if (col == 5) break;
                var from = moveViewportRight ? new Point(530, 440) : new Point(220, 440);
                var to = moveViewportRight ? new Point(220, 440) : new Point(530, 440);
                _hwnd = await ResolveRequiredGameWindowAsync(ct);
                _input.DragClientPoint(_hwnd, from, to, 850);
                await Task.Delay(600, ct);
                using var after = await CaptureGameWindowAsync(ct);
                double diff = MapFrameDifference(frame, after);
                edgeStable = diff <= EdgeThreshold ? edgeStable + 1 : 0;
                Log?.Invoke($"[던전 자동이동] 가로 탐색 row={row + 1}, step={col + 1} · 화면변화={diff:0.00} · 경계={edgeStable}/2");
                if (edgeStable >= 2) break;
            }

            using (var last = await CaptureGameWindowAsync(ct))
            {
                var found = await _detector.DetectAsync(mapTarget, last, ct);
                if (found.Found) return found;
            }
            if (row == 3) break;

            using var beforeDown = await CaptureGameWindowAsync(ct);
            _hwnd = await ResolveRequiredGameWindowAsync(ct);
            _input.DragClientPoint(_hwnd, new Point(380, 650), new Point(380, 320), 850);
            await Task.Delay(650, ct);
            using var afterDown = await CaptureGameWindowAsync(ct);
            double downDiff = MapFrameDifference(beforeDown, afterDown);
            Log?.Invoke($"[던전 자동이동] 다음 줄 이동 {row + 1}-> {row + 2} · 화면변화={downDiff:0.00}");
            if (downDiff <= EdgeThreshold)
            {
                using var confirmBefore = await CaptureGameWindowAsync(ct);
                _input.DragClientPoint(_hwnd, new Point(380, 650), new Point(380, 320), 850);
                await Task.Delay(650, ct);
                using var confirmAfter = await CaptureGameWindowAsync(ct);
                double confirmDiff = MapFrameDifference(confirmBefore, confirmAfter);
                Log?.Invoke($"[던전 자동이동] 세로 경계 재확인 · 화면변화={confirmDiff:0.00}");
                if (confirmDiff <= EdgeThreshold) break;
            }
            moveViewportRight = !moveViewportRight;
        }

        return DetectionResult.NotFound;
    }

    // The map label is an OCR anchor only. This validates the colored dungeon icon above it.
    // Purple is the normal state; the selected/highlight state can render blue, so both are accepted.
    private static bool TryFindDungeonIconAboveLabel(Bitmap frame, Rectangle labelBounds, out Rectangle iconBounds)
    {
        iconBounds = Rectangle.Empty;
        if (labelBounds.Width <= 0 || labelBounds.Height <= 0) return false;

        int centerX = labelBounds.Left + labelBounds.Width / 2;
        int searchWidth = Math.Max(120, labelBounds.Width + 100);
        var search = WindowCapture.ClampRoi(
            new Rectangle(centerX - searchWidth / 2, labelBounds.Top - 105, searchWidth, 105),
            frame.Size);
        if (search.Width < 20 || search.Height < 20) return false;

        int minX = int.MaxValue, minY = int.MaxValue;
        int maxX = int.MinValue, maxY = int.MinValue;
        int pixels = 0;

        for (int y = search.Top; y < search.Bottom; y++)
        {
            for (int x = search.Left; x < search.Right; x++)
            {
                Color c = frame.GetPixel(x, y);
                bool purpleOrBlue =
                    c.B >= 140 &&
                    c.B > c.G * 1.12 &&
                    c.G < 190 &&
                    (c.R >= 65 || c.B >= 210);

                if (!purpleOrBlue) continue;
                pixels++;
                if (x < minX) minX = x;
                if (x > maxX) maxX = x;
                if (y < minY) minY = y;
                if (y > maxY) maxY = y;
            }
        }

        if (pixels < 120 || minX == int.MaxValue) return false;

        var bounds = Rectangle.FromLTRB(minX, minY, maxX + 1, maxY + 1);
        if (bounds.Width < 18 || bounds.Height < 18 || bounds.Width > 85 || bounds.Height > 85)
            return false;

        // The icon must actually be above the OCR text, not beside/below it.
        if (bounds.Bottom > labelBounds.Top + 4)
            return false;

        iconBounds = bounds;
        return true;
    }

'''
engine = engine[:ss] + generic_search + engine[se:]

engine = engine.replace('[페카 자동이동] 울라 월드맵 좌상단 끝 정렬 시작', '[던전 자동이동] 울라 월드맵 좌상단 끝 정렬 시작')
engine = engine.replace('[페카 자동이동] 좌상단 정렬', '[던전 자동이동] 좌상단 정렬')
engine = engine.replace('[페카 자동이동] 화면 변화 거의 없음 2회 연속', '[던전 자동이동] 화면 변화 거의 없음 2회 연속')
engine = engine.replace('[페카 자동이동] 동시 확인:', '[던전 자동이동] 동시 확인:')
write(engine_path, engine)

# 3) Runda/Fiod map, popup, arrival, 1-1/2-1 and exact entry-text OCR targets.
targets = json.loads(read(targets_path))
new_targets = [
    {"Id":"route_runda_map","Kind":"ocr","Roi":{"X":20,"Y":110,"Width":660,"Height":650},"Text":"룬다 던전","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_fiod_map","Kind":"ocr","Roi":{"X":20,"Y":110,"Width":660,"Height":650},"Text":"피오드 던전","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_runda_popup_title","Kind":"ocr","Roi":{"X":90,"Y":480,"Width":620,"Height":320},"Text":"룬다 던전","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_fiod_popup_title","Kind":"ocr","Roi":{"X":90,"Y":480,"Width":620,"Height":320},"Text":"피오드 던전","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_runda_title","Kind":"ocr","Roi":{"X":0,"Y":0,"Width":330,"Height":150},"Text":"룬다 던전","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_fiod_title","Kind":"ocr","Roi":{"X":0,"Y":0,"Width":330,"Height":150},"Text":"피오드 던전","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_regular_1_1","Kind":"ocr","Roi":{"X":220,"Y":500,"Width":220,"Height":180},"Text":"1-1","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_regular_2_1","Kind":"ocr","Roi":{"X":250,"Y":700,"Width":230,"Height":200},"Text":"2-1","MaxEditDistance":1,"OcrRetryAt2x":True},
    {"Id":"route_enter_regular_1_1","Kind":"ocr","Roi":{"X":100,"Y":870,"Width":600,"Height":130},"Text":"1층 1구역 진입","MaxEditDistance":2,"OcrRetryAt2x":True},
    {"Id":"route_enter_regular_2_1","Kind":"ocr","Roi":{"X":100,"Y":870,"Width":600,"Height":130},"Text":"2층 1구역 진입","MaxEditDistance":2,"OcrRetryAt2x":True},
]
ids = {x["Id"] for x in new_targets}
targets = [x for x in targets if x.get("Id") not in ids] + new_targets
write(targets_path, json.dumps(targets, ensure_ascii=False, indent=2) + "\n")

# 4) Repair the updater contract. V0.1.36's release-only package exposed a flaw in the
# old updater: it always deleted tools/ and FishingAutomation/ even when the incoming
# package did not contain replacements. That makes the next update impossible.
updater = read(updater_path)
updater = replace_once(
    updater,
    '''    foreach ($name in @('release','FishingAutomation','tools')) {
        Remove-Item -LiteralPath (Join-Path $InstallRoot $name) -Recurse -Force -ErrorAction SilentlyContinue
    }

    Get-ChildItem -LiteralPath $sourceRoot -Force | ForEach-Object {
''',
    '''    # V0.1.37: only delete install directories that the incoming package actually replaces.
    # This keeps tools/ApplyUpdate.ps1 and source/config files alive for release-only packages.
    foreach ($name in @('release','FishingAutomation','tools')) {
        $incoming = Join-Path $sourceRoot $name
        if (Test-Path -LiteralPath $incoming) {
            Remove-Item -LiteralPath (Join-Path $InstallRoot $name) -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    Get-ChildItem -LiteralPath $sourceRoot -Force | ForEach-Object {
''',
    "safe updater replacement directories")
write(updater_path, updater)

# Version bump.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.36", "V0.1.37")
                   .replace("0.1.36.0", "0.1.37.0")
                   .replace("0.1.36", "0.1.37"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.37_DUNGEON_ICON_RUNDA_FIOD.txt").write_text(
    "MABI AUTO V0.1.37 - DUNGEON MAP ICON + RUNDA/FIOD 1-1/2-1\n\n"
    "Fixes the sidebar '인식 테스트' text truncation by removing the unused icon reservation and slightly widening that button.\n"
    "World-map dungeon names are now OCR anchors only. The program validates and clicks the colored dungeon icon directly above the recognized text; it never clicks the text or a fallback coordinate.\n"
    "Adds Runda 1-1, Runda 2-1, Fiod 1-1 and Fiod 2-1 destinations. Only 1-1/2-1 are recognized; 1-2/1-3/2-2/2-3 are not used.\n"
    "Exact '1층 1구역 진입' or '2층 1구역 진입' confirmation is required before Space.\n"
    "Existing Peaca D1-1/D2-1, recognition tests, runtime error upload, retry fast path, Abyss, fishing and F10 behavior are preserved.\n",
    encoding="utf-8"
)

# Structural guards.
main_check = read(main_path)
ref_check = read(refui_path)
engine_check = read(engine_path)
targets_check = json.loads(read(targets_path))
joined_targets = {x.get("Id") for x in targets_check}

for marker in ("runda_d1_1","runda_d2_1","fiod_d1_1","fiod_d2_1"):
    if marker not in main_check:
        raise RuntimeError(f"destination mapping missing: {marker}")
for label in ("룬다 1-1","룬다 2-1","피오드 1-1","피오드 2-1"):
    if label not in ref_check:
        raise RuntimeError(f"destination UI missing: {label}")
if 'AddButton("인식 테스트", new(18, 511, 178, 59), owner.ShowVisualRecognitionTest, "", "nav");' not in ref_check:
    raise RuntimeError("visual-test sidebar hotfix missing")
for marker in (
    "DUNGEON_WORLD_ROUTE_V11",
    "TryFindDungeonIconAboveLabel",
    "위 던전 아이콘 클릭",
    "글씨나 대체 좌표를 누르지 않고 정지",
    "FindDungeonOnWorldMapAsync",
    "route_regular_1_1",
    "route_regular_2_1",
    "route_enter_regular_1_1",
    "route_enter_regular_2_1",
):
    if marker not in engine_check:
        raise RuntimeError(f"engine marker missing: {marker}")
for forbidden in ("RunPeacaPreRouteAsync", "FindPeacaOnWorldMapAsync", "글자 위치 클릭"):
    if forbidden in engine_check:
        raise RuntimeError(f"old direct-text route residue remains: {forbidden}")
for tid in (
    "route_runda_map","route_fiod_map","route_runda_popup_title","route_fiod_popup_title",
    "route_runda_title","route_fiod_title","route_regular_1_1","route_regular_2_1",
    "route_enter_regular_1_1","route_enter_regular_2_1",
):
    if tid not in joined_targets:
        raise RuntimeError(f"target missing: {tid}")

updater_check = read(updater_path)
if "only delete install directories that the incoming package actually replaces" not in updater_check:
    raise RuntimeError("safe updater replacement guard missing")
if "$incoming = Join-Path $sourceRoot $name" not in updater_check:
    raise RuntimeError("incoming-package directory guard missing")

print("V0.1.37 patch applied: UI text + icon click + Runda/Fiod 1-1/2-1 + updater self-repair")
