#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0131_peaca_drag_interface_fix.py SOURCE_ROOT")

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
input_path = app / "dungeon" / "InputController.cs"
engine_path = app / "dungeon" / "ScenarioEngine.cs"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


input_cs = read(input_path)
iface_line = "    void DragClientPoint(nint hwnd, Point from, Point to, int durationMs);\n"
if iface_line not in input_cs:
    raise RuntimeError("V0.1.31 drag interface line missing")
# The map drag is deliberately Interception-only. Keeping it off IInputController means
# the existing SendInputFallback does not silently perform a lower-trust map drag.
input_cs = input_cs.replace(iface_line, "", 1)
if "public void DragClientPoint(nint hwnd, Point from, Point to, int durationMs)" not in input_cs:
    raise RuntimeError("Interception DragClientPoint implementation missing")
write(input_path, input_cs)

engine = read(engine_path)
if "_input.DragClientPoint(" not in engine:
    raise RuntimeError("ScenarioEngine direct drag calls missing")
engine = engine.replace("_input.DragClientPoint(_hwnd, ", "DragPeacaMap(")

anchor = "    private static double PeacaMapFrameDifference(Bitmap a, Bitmap b)\n"
if anchor not in engine:
    raise RuntimeError("PeacaMapFrameDifference anchor missing")
helper = '''    private void DragPeacaMap(Point from, Point to, int durationMs)
    {
        if (_input is not InterceptionInput interception)
            throw new InvalidOperationException("페카 자동 지도 이동은 Interception 마우스 입력이 필요합니다. 드라이버 입력 상태를 확인하세요.");
        interception.DragClientPoint(_hwnd, from, to, durationMs);
    }

'''
engine = engine.replace(anchor, helper + anchor, 1)
if "_input.DragClientPoint(" in engine:
    raise RuntimeError("direct IInputController drag call remains")
write(engine_path, engine)

print("V0.1.31 drag fix applied: map dragging remains Interception-only without changing fallback interface")
