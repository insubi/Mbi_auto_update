#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0132_ulla_fixed_click_final.py SOURCE_ROOT")

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

        // V0.1.32: the local-map Ula breadcrumb is fixed in the 800x1000 client.
        // The tiny white breadcrumb text is no longer an OCR hard gate. Instead, verify
        // the actual screen transition after M and after the fixed breadcrumb click.
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
write(engine_path, engine)

# Bump runtime version labels while keeping behavior identifiers intact.
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
    if changed != text:
        write(path, changed)

changes = root / "CHANGES_V0.1.32_ULLA_FIXED_CLICK.txt"
changes.write_text(
    "MABI AUTO V0.1.32 - ULA BREADCRUMB FIX\n\n"
    "Fixes the false stop where the local map was visibly open and 'Ula Continent / Sen Mag Plain' was visible, but OCR missed the small top-left breadcrumb.\n"
    "The Peaca pre-route now presses M, verifies a real screen transition, clicks the user-confirmed fixed Ula breadcrumb point (82,66), verifies the continent-map transition by frame difference, then continues the existing bounded map search.\n"
    "Peaca D1-1 and D2-1 only, exact entry verification, dungeon handoff, Abyss, fishing, F10, retry and scene-skip behavior are preserved from V0.1.31.\n",
    encoding="utf-8"
)

check = read(engine_path)
for forbidden in (
    "M 입력 후 좌측 상단 '울라 대륙'을 확인하지 못했습니다",
    'DetectAsync("route_ulla_continent", first',
    'ulla.Center',
    'peaca_d2_2',
    'route_d2_2',
    'route_enter_d2_2',
):
    if forbidden in check:
        raise RuntimeError(f"forbidden V0.1.31/D2-2 residue remains: {forbidden}")

for required in (
    'var ullaBreadcrumbPoint = new Point(82, 66);',
    'M 입력 후 화면변화=',
    '울라 대륙 클릭 후 화면변화=',
    'await AlignWorldMapTopLeftAsync(ct);',
    'peaca_d1_1',
    'peaca_d2_1',
    '기존 던전 매크로 초입 확인 완료',
):
    if required not in check:
        raise RuntimeError(f"V0.1.32 required marker missing: {required}")

print("V0.1.32 patch applied: fixed Ula breadcrumb (82,66) + screen-transition verification")
