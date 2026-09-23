#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
telegram_path = app / "MainForm.Telegram.cs"
project_path = app / "FishingAutomation.csproj"
update_path = app / "UpdateManager.cs"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
           {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
before = {p.relative_to(root).as_posix(): digest(p) for p in tracked}

telegram = read(telegram_path)
if 'case "/stone":' not in telegram:
    raise SystemExit("/stone command marker missing")
telegram = telegram.replace('case "/stone":', 'case "/item":', 1)
if 'case "/stonereset":' not in telegram:
    raise SystemExit("/stonereset command must remain")
write(telegram_path, telegram)

project = read(project_path)
for old, new in (
    ("<Version>0.1.68</Version>", "<Version>0.1.69</Version>"),
    ("<AssemblyVersion>0.1.68.0</AssemblyVersion>", "<AssemblyVersion>0.1.69.0</AssemblyVersion>"),
    ("<FileVersion>0.1.68.0</FileVersion>", "<FileVersion>0.1.69.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.68"' not in update:
    raise SystemExit("UpdateManager V0.1.68 marker missing")
update = update.replace('CurrentVersion = "V0.1.68"', 'CurrentVersion = "V0.1.69"', 1)
write(update_path, update)

patched = read(telegram_path)
if 'case "/item":' not in patched:
    raise SystemExit("/item command not added")
if 'case "/stone":' in patched:
    raise SystemExit("old /stone command still present")
if 'case "/stonereset":' not in patched:
    raise SystemExit("/stonereset was changed unexpectedly")

allowed = {
    telegram_path.relative_to(root).as_posix(),
    project_path.relative_to(root).as_posix(),
    update_path.relative_to(root).as_posix(),
}
after_tracked = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in
                 {".cs", ".csproj", ".json", ".ps1", ".cmd", ".bat"}]
after = {p.relative_to(root).as_posix(): digest(p) for p in after_tracked}
changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
unexpected = sorted(changed - allowed)
if unexpected:
    raise SystemExit("unexpected runtime/source changes: " + ", ".join(unexpected))

print("V0.1.69 applied: Telegram /stone renamed to /item; /stonereset unchanged")
