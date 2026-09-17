#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0132_ulla_fixed_breadcrumb.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
engine_path = app / "dungeon" / "ScenarioEngine.cs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)

engine = read(engine_path)
old = '''        // Already-open map is accepted. Otherwise M is sent exactly once and verified.
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
'''
new = '''        // V0.1.32: the breadcrumb position is fixed on the 800x1000 client.
        // OCR is still used only as an optional "map already open" hint, but it is no longer a hard gate.
        // This avoids false stops when the small white breadcrumb text is visually present but Windows OCR misses it.
        bool mapAlreadyOpen = false;
        using (var first = await CaptureGameWindowAsync(ct))
        {
            var mapOpen = await _detector.DetectAsync("route_ulla_continent", first, ct);
            mapAlreadyOpen = mapOpen.Found;
        }

        if (!mapAlreadyOpen)
        {
            Log?.Invoke("[페카 자동이동] M 입력 -> 지도 열기");
            _input.TapScanCode(0x32); // M
            await Task.Delay(1000, ct);
        }
        else
        {
            Log?.Invoke("[페카 자동이동] 지도 열림 OCR 확인 -> M 입력 생략");
        }

        _hwnd = await ResolveRequiredGameWindowAsync(ct);
        NativeMethods.SetForegroundWindow(_hwnd);
        var ullaBreadcrumbPoint = new Point(86, 62);
        Log?.Invoke($"[페카 자동이동] 좌측 상단 고정 '울라 대륙' 클릭 @ {ullaBreadcrumbPoint}");
        _input.ClickClientPoint(_hwnd, ullaBreadcrumbPoint);
        await Task.Delay(1000, ct);
'''
engine = replace_once(engine, old, new, "Ula breadcrumb gate replacement")
write(engine_path, engine)

# Version bump for runtime-owned text/config files only.
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

(root / "CHANGES_V0.1.32_ULLA_FIXED_BREADCRUMB.txt").write_text(
    "MABI AUTO V0.1.32 - ULA BREADCRUMB OCR FALSE-STOP FIX\n\n"
    "Fixes the Peaca auto-route stopping immediately after M when the visible top-left 'Ula Continent' breadcrumb is missed by OCR.\n"
    "The 800x1000 client now clicks the user-confirmed fixed Ula breadcrumb point (86,62) after opening the map. OCR remains only an optional already-open-map hint and is no longer a hard requirement.\n"
    "After the fixed breadcrumb click, the existing bounded top-left alignment, serpentine Peaca OCR search, Peaca Tomb + Go Here verification, D1-1/D2-1 selection, exact entry verification, and existing dungeon handoff are unchanged.\n"
    "No blind dungeon fallback click was added. Existing dungeon/Abyss/fishing behavior and the removal of policy/ERROR88 detection are preserved.\n",
    encoding="utf-8"
)

# Hard validation against regression.
final_engine = read(engine_path)
for required in (
    'var ullaBreadcrumbPoint = new Point(86, 62);',
    "좌측 상단 고정 '울라 대륙' 클릭",
    'peaca_d1_1',
    'peaca_d2_1',
    'route_d1_1',
    'route_d2_1',
    '기존 던전 매크로 초입 확인 완료',
):
    if required not in final_engine:
        raise RuntimeError(f"required V0.1.32 marker missing: {required}")

for forbidden in (
    "M 입력 후 좌측 상단 '울라 대륙'을 확인하지 못했습니다",
    'peaca_d2_2',
    'route_d2_2',
    'route_enter_d2_2',
):
    if forbidden in final_engine:
        raise RuntimeError(f"forbidden regression remains: {forbidden}")

print("V0.1.32 patch applied: fixed Ula breadcrumb click at client (86,62), OCR hard gate removed")
