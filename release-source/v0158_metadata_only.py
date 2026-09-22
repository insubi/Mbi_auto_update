#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.57</Version>", "<Version>0.1.58</Version>"),
    ("<AssemblyVersion>0.1.57.0</AssemblyVersion>", "<AssemblyVersion>0.1.58.0</AssemblyVersion>"),
    ("<FileVersion>0.1.57.0</FileVersion>", "<FileVersion>0.1.58.0</FileVersion>"),
):
    if old not in p:
        raise SystemExit(f"project version marker missing: {old}")
    p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
u = read(update)
if 'CurrentVersion = "V0.1.57"' not in u:
    raise SystemExit("UpdateManager V0.1.57 marker missing")
u = u.replace('CurrentVersion = "V0.1.57"', 'CurrentVersion = "V0.1.58"', 1)
write(update, u)

print("V0.1.58 metadata applied; runtime behavior unchanged")
