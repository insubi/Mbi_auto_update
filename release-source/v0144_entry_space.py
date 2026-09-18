#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0144_entry_space.py SOURCE_ROOT")

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

old = '''                    else
                    {
                        if (step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase))
                        {
                            string exactEntry = FuzzyText.Normalize(found.ReadText ?? "");
                            var entryClickSafe = new Rectangle(360, 900, 440, 100);

                            if (!exactEntry.Equals(FuzzyText.Normalize("입장하기"), StringComparison.OrdinalIgnoreCase))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기 정확 단어 확인 실패 -> 클릭 안 함 · OCR={found.ReadText} @ {found.Bounds}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            if (!entryClickSafe.Contains(found.Center))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기가 오른쪽 하단 안전영역 밖 -> 클릭 안 함 @ {found.Center} safe={entryClickSafe}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            Log?.Invoke($"[던전 입장] 오른쪽 입장하기 단어 자체 중앙만 클릭 @ {found.Bounds} center={found.Center}");
                        }

                        _input.ClickClientPoint(_hwnd, found.Center);
                        await Task.Delay(_settings.ClickSettleMs, ct);
                    }
'''

new = '''                    else
                    {
                        if (step.Target.Equals("enter_bottom", StringComparison.OrdinalIgnoreCase))
                        {
                            string exactEntry = FuzzyText.Normalize(found.ReadText ?? "");
                            var entryKeySafe = new Rectangle(360, 900, 440, 100);

                            if (!exactEntry.Equals(FuzzyText.Normalize("입장하기"), StringComparison.OrdinalIgnoreCase))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기 정확 단어 확인 실패 -> Space 안 누름 · OCR={found.ReadText} @ {found.Bounds}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            if (!entryKeySafe.Contains(found.Center))
                            {
                                Log?.Invoke($"[던전 입장] 입장하기가 오른쪽 하단 안전영역 밖 -> Space 안 누름 @ {found.Center} safe={entryKeySafe}");
                                await Task.Delay(Math.Max(250, _settings.PollIntervalMs), ct);
                                continue;
                            }

                            Log?.Invoke($"[던전 입장] 도전 상태 + 오른쪽 입장하기 확인 -> Space 입력 @ {found.Bounds}");
                            _input.TapScanCode(0x39);
                            await Task.Delay(_settings.ClickSettleMs, ct);
                        }
                        else
                        {
                            _input.ClickClientPoint(_hwnd, found.Center);
                            await Task.Delay(_settings.ClickSettleMs, ct);
                        }
                    }
'''

engine = replace_once(engine, old, new, "enter-bottom mouse to Space")
write(engine_path, engine)

for path in root.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".cs", ".csproj", ".json", ".cmd", ".ps1", ".txt"}:
        continue
    try:
        text = read(path)
    except UnicodeDecodeError:
        continue
    changed = (text.replace("V0.1.43", "V0.1.44")
                   .replace("0.1.43.0", "0.1.44.0")
                   .replace("0.1.43", "0.1.44"))
    if changed != text:
        write(path, changed)

(root / "CHANGES_V0.1.44_ENTRY_SPACE.txt").write_text(
    "MABI AUTO V0.1.44 - ENTER WITH SPACE\n\n"
    "Dungeon entry keeps the selected -> challenge state flow.\n"
    "The selected card button may still be clicked only inside its safe card region.\n"
    "After challenge is confirmed and the exact right-bottom '입장하기' word is detected, the bot no longer mouse-clicks that text.\n"
    "It sends the Space scan code (0x39), matching the in-game Space prompt.\n"
    "The left '파티 찾기' button can therefore never be activated by the entry mouse-click path because that path no longer performs a mouse click.\n"
    "Right-bottom OCR/safe-region checks remain before Space is allowed.\n"
    "Recognition nav UI remains '인식' with the image icon.\n",
    encoding="utf-8"
)

check = read(engine_path)
for marker in (
    "도전 상태 + 오른쪽 입장하기 확인 -> Space 입력",
    "_input.TapScanCode(0x39);",
    "Space 안 누름",
):
    if marker not in check:
        raise RuntimeError("entry Space marker missing: " + marker)

if "오른쪽 입장하기 단어 자체 중앙만 클릭" in check:
    raise RuntimeError("old entry mouse-click log remains")

print("V0.1.44 patch applied: challenge + exact entry -> Space, no entry mouse click")
