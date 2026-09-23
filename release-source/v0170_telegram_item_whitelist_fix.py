#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"
notifier_path = app / "TelegramNotifier.cs"
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

notifier = read(notifier_path)
old_whitelist = 'if (command is not ("/status" or "/stop" or "/restart" or "/help")) continue;'
new_whitelist = 'if (command is not ("/status" or "/stop" or "/restart" or "/help" or "/item" or "/itemreset")) continue;'
if old_whitelist not in notifier:
    raise SystemExit("Telegram whitelist marker missing")
notifier = notifier.replace(old_whitelist, new_whitelist, 1)

old_help = 'reply = "MABI AUTO 원격 명령\\n/status - 현재 상태\\n/stop - 매크로 정지\\n/restart - 현재 선택 모드 재시작";'
new_help = 'reply = "MABI AUTO 원격 명령\\n/status - 현재 상태\\n/item - 전리품 획득 현황\\n/itemreset - 전리품 누적 초기화\\n/stop - 매크로 정지\\n/restart - 현재 선택 모드 재시작";'
if old_help not in notifier:
    raise SystemExit("Telegram help marker missing")
notifier = notifier.replace(old_help, new_help, 1)
write(notifier_path, notifier)

telegram = read(telegram_path)
for marker in ('case "/item":', 'case "/itemreset":'):
    if marker not in telegram:
        raise SystemExit(f"MainForm Telegram command missing: {marker}")
for old in ('case "/stone":', 'case "/stonereset":'):
    if old in telegram:
        raise SystemExit(f"old Telegram command remains unexpectedly: {old}")

project = read(project_path)
for old, new in (
    ("<Version>0.1.69</Version>", "<Version>0.1.70</Version>"),
    ("<AssemblyVersion>0.1.69.0</AssemblyVersion>", "<AssemblyVersion>0.1.70.0</AssemblyVersion>"),
    ("<FileVersion>0.1.69.0</FileVersion>", "<FileVersion>0.1.70.0</FileVersion>"),
):
    if old not in project:
        raise SystemExit(f"project version marker missing: {old}")
    project = project.replace(old, new, 1)
write(project_path, project)

update = read(update_path)
if 'CurrentVersion = "V0.1.69"' not in update:
    raise SystemExit("UpdateManager V0.1.69 marker missing")
update = update.replace('CurrentVersion = "V0.1.69"', 'CurrentVersion = "V0.1.70"', 1)
write(update_path, update)

patched = read(notifier_path)
for marker in ('"/item"', '"/itemreset"', '/item - 전리품 획득 현황', '/itemreset - 전리품 누적 초기화'):
    if marker not in patched:
        raise SystemExit(f"required Telegram notifier marker missing: {marker}")

allowed = {
    notifier_path.relative_to(root).as_posix(),
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

print("V0.1.70 applied: Telegram receive whitelist now accepts /item and /itemreset")
