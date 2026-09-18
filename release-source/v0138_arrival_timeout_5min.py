#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0138_arrival_timeout_5min.py SOURCE_ROOT")

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
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)

engine = read(engine_path)

engine = replace_once(
    engine,
    'bool arrived = await WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 30, ct);',
    'bool arrived = await WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 300, ct);',
    "Peaca arrival timeout")
engine = replace_once(
    engine,
    'throw new TimeoutException("이동 후 30초 안에 페카 고분 도착/심층 던전 탭을 확인하지 못했습니다.");',
    'throw new TimeoutException("이동 후 5분 안에 페카 고분 도착/심층 던전 탭을 확인하지 못했습니다.");',
    "Peaca timeout message")
engine = replace_once(
    engine,
    'var arrived = await WaitForTargetAsync(arrivalTarget, 30, ct);',
    'var arrived = await WaitForTargetAsync(arrivalTarget, 300, ct);',
    "Runda/Fiod arrival timeout")
engine = replace_once(
    engine,
    'throw new TimeoutException($"이동 후 30초 안에 {dungeonName} 도착 화면을 확인하지 못했습니다.");',
    'throw new TimeoutException($"이동 후 5분 안에 {dungeonName} 도착 화면을 확인하지 못했습니다.");',
    "Runda/Fiod timeout message")
write(engine_path, engine)

# Version bump from the current release line.
for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.37", "V0.1.38")
                   .replace("0.1.37.0", "0.1.38.0")
                   .replace("0.1.37", "0.1.38"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.38_ARRIVAL_TIMEOUT_5MIN.txt").write_text(
    "MABI AUTO V0.1.38 - DUNGEON ARRIVAL TIMEOUT 5 MINUTES\n\n"
    "Changes dungeon travel arrival verification from 30 seconds to 5 minutes (300 seconds).\n"
    "Applies to Peaca Tomb, Runda Dungeon and Fiod Dungeon auto-route arrival waits.\n"
    "All V0.1.37 dungeon-icon clicking, Runda/Fiod 1-1/2-1, recognition UI, updater-survival and safety behavior are preserved.\n",
    encoding="utf-8"
)

check = read(engine_path)
for marker in (
    'WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 300, ct)',
    'WaitForTargetAsync(arrivalTarget, 300, ct)',
    '이동 후 5분 안에 페카 고분 도착/심층 던전 탭',
    '이동 후 5분 안에 {dungeonName} 도착 화면',
):
    if marker not in check:
        raise RuntimeError("V0.1.38 timeout marker missing: " + marker)

for forbidden in (
    'WaitForTargetPairAsync(arrivalTarget, "route_deep_tab", 30, ct)',
    'WaitForTargetAsync(arrivalTarget, 30, ct)',
    '이동 후 30초 안에 페카 고분',
    '이동 후 30초 안에 {dungeonName}',
):
    if forbidden in check:
        raise RuntimeError("old 30-second arrival timeout remains: " + forbidden)

print("V0.1.38 patch applied: dungeon arrival wait 30s -> 300s")
