#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0132_peaca_breadcrumb_fixed_click.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

engine = read(engine_path)
old = '''        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);

        // Already-open map is accepted. Otherwise M is sent exactly once and verified.
        using (var first = await CaptureGameWindowAsync(ct))
        {
            var mapOpen = await _detector.DetectAsync("route_ulla_continent", first, ct);
            if (!mapOpen.Found)
            {
                Log?.Invoke("[페카 자동이동] M 입력 -> 지도 열기");
                _input.TapScanCode(0x32); // M
                await Task.Delay(1000, ct);
            }
        }

        DetectionResult ulla;
        using (var mapFrame = await CaptureGameWindowAsync(ct))
            ulla = await _detector.DetectAsync("route_ulla_continent", mapFrame, ct);
        if (!ulla.Found)
            throw new TimeoutException("M 입력 후 좌측 상단 '울라 대륙'을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        Log?.Invoke($"[페카 자동이동] 울라 대륙 확인 -> 클릭 @ {ulla.Bounds}");
        _input.ClickClientPoint(_hwnd, ulla.Center);
        await Task.Delay(1000, ct);

        await AlignWorldMapTopLeftAsync(ct);
'''
new = '''        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);

        // V0.1.32: The local-map breadcrumb is fixed at the top-left.
        // Do not depend on OCR here; validate the two screen transitions by frame change instead.
        using var beforeMapOpen = await CaptureGameWindowAsync(ct);
        Log?.Invoke("[페카 자동이동] M 입력 -> 지도 열기");
        _input.TapScanCode(0x32); // M
        await Task.Delay(1200, ct);

        using var localMapFrame = await CaptureGameWindowAsync(ct);
        double mapOpenDiff = MapFrameDifference(beforeMapOpen, localMapFrame);
        Log?.Invoke($"[페카 자동이동] M 입력 후 화면변화={mapOpenDiff:0.00}");
        if (mapOpenDiff <= 6.0)
            throw new TimeoutException("M 입력 후 지도 화면 전환을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        var ullaBreadcrumbPoint = new Point(82, 66);
        Log?.Invoke($"[페카 자동이동] 좌측 상단 울라 대륙 고정 위치 클릭 @ {ullaBreadcrumbPoint}");
        _input.ClickClientPoint(_hwnd, ullaBreadcrumbPoint);
        await Task.Delay(1200, ct);

        using var worldMapFrame = await CaptureGameWindowAsync(ct);
        double continentOpenDiff = MapFrameDifference(localMapFrame, worldMapFrame);
        Log?.Invoke($"[페카 자동이동] 울라 대륙 클릭 후 화면변화={continentOpenDiff:0.00}");
        if (continentOpenDiff <= 6.0)
            throw new TimeoutException("좌측 상단 울라 대륙 고정 위치 클릭 후 월드맵 전환을 확인하지 못했습니다. 임의 좌표를 클릭하지 않고 정지합니다.");

        await AlignWorldMapTopLeftAsync(ct);
'''

if old not in engine:
    raise RuntimeError("V0.1.32 map-open replacement anchor missing")
engine = engine.replace(old, new, 1)

# Bump runtime version labels only; preserve unrelated feature identifiers.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.31", "V0.1.32")
                   .replace("0.1.31.0", "0.1.32.0")
                   .replace("0.1.31", "0.1.32"))
    if path == engine_path:
        changed = engine.replace("V0.1.31", "V0.1.32").replace("0.1.31.0", "0.1.32.0").replace("0.1.31", "0.1.32")
    if changed != text:
        write(path, changed)

changes = root / "CHANGES_V0.1.32_PEACA_BREADCRUMB_FIXED_CLICK.txt"
changes.write_text(
    "MABI AUTO V0.1.32 - PEACA MAP OPEN FIX\n\n"
    "Fixes the false stop seen when the map was visibly open but OCR failed to read the fixed top-left Ula continent breadcrumb.\n"
    "The Peaca pre-route now presses M, verifies a real screen transition, clicks the fixed Ula-continent breadcrumb position (82,66), verifies the continent-map transition by image difference, then continues the existing top-left alignment and OCR search.\n"
    "No fallback blind target click is used after the breadcrumb step; transition failure stops safely.\n"
    "Peaca D1-1 / D2-1, existing dungeon handoff, Abyss, fishing, F10, retry and scene-skip behavior are preserved from V0.1.31.\n",
    encoding="utf-8"
)

check = read(engine_path)
for forbidden in (
    "M 입력 후 좌측 상단 '울라 대륙'을 확인하지 못했습니다",
    'DetectAsync("route_ulla_continent", first',
    'ulla.Center',
):
    if forbidden in check:
        raise RuntimeError(f"old Ula OCR dependency remains: {forbidden}")
for required in (
    "var ullaBreadcrumbPoint = new Point(82, 66);",
    "M 입력 후 화면변화=",
    "울라 대륙 클릭 후 화면변화=",
    "await AlignWorldMapTopLeftAsync(ct);",
):
    if required not in check:
        raise RuntimeError(f"V0.1.32 required marker missing: {required}")

print("V0.1.32 patch applied: fixed Ula breadcrumb click + frame-change verification")
