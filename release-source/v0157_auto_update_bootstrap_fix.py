#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

# 1) Add a bootstrap START.cmd to the package root.
start_cmd = root / "START.cmd"
start_cmd.write_text(
    '@echo off\r\n'
    'setlocal\r\n'
    'cd /d "%~dp0"\r\n'
    'if not exist "%~dp0release\\FishingAutomation.exe" (\r\n'
    '  echo [MABI AUTO] release\\FishingAutomation.exe not found.\r\n'
    '  exit /b 1\r\n'
    ')\r\n'
    'start "" "%~dp0release\\FishingAutomation.exe"\r\n'
    'exit /b 0\r\n',
    encoding="utf-8"
)

# 2) Harden future updater restart: prefer START.cmd, fallback to EXE directly.
updater = root / "tools" / "ApplyUpdate.ps1"
u = read(updater)
anchor = '''function Log([string]$text) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $text" | Tee-Object -FilePath $log -Append | Out-Null
}
'''
insert = '''function Log([string]$text) {
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $text" | Tee-Object -FilePath $log -Append | Out-Null
}

function Start-MabiAuto {
    $startCmd = Join-Path $InstallRoot 'START.cmd'
    if (Test-Path -LiteralPath $startCmd) {
        Log 'Starting MABI AUTO through START.cmd.'
        Start-Process -FilePath $startCmd -WorkingDirectory $InstallRoot
        return
    }

    $exe = Join-Path $InstallRoot 'release\FishingAutomation.exe'
    if (Test-Path -LiteralPath $exe) {
        Log 'START.cmd missing; starting release\FishingAutomation.exe directly.'
        Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe -Parent)
        return
    }

    throw '업데이트 후 실행 파일을 찾지 못했습니다. START.cmd와 release\FishingAutomation.exe가 모두 없습니다.'
}
'''
if anchor not in u:
    raise SystemExit("ApplyUpdate Log anchor missing")
u = u.replace(anchor, insert, 1)

old_restart = "Start-Process -FilePath (Join-Path $InstallRoot 'START.cmd') -WorkingDirectory $InstallRoot"
count = u.count(old_restart)
if count != 3:
    raise SystemExit(f"expected 3 old START.cmd restart calls, found {count}")
u = u.replace(old_restart, "Start-MabiAuto")
write(updater, u)

# 3) Metadata-only version bump.
project = app / "FishingAutomation.csproj"
p = read(project)
for old, new in (
    ("<Version>0.1.56</Version>", "<Version>0.1.57</Version>"),
    ("<AssemblyVersion>0.1.56.0</AssemblyVersion>", "<AssemblyVersion>0.1.57.0</AssemblyVersion>"),
    ("<FileVersion>0.1.56.0</FileVersion>", "<FileVersion>0.1.57.0</FileVersion>"),
):
    if old not in p:
        raise SystemExit(f"project version marker missing: {old}")
    p = p.replace(old, new, 1)
write(project, p)

update = app / "UpdateManager.cs"
m = read(update)
if 'CurrentVersion = "V0.1.56"' not in m:
    raise SystemExit("UpdateManager V0.1.56 marker missing")
m = m.replace('CurrentVersion = "V0.1.56"', 'CurrentVersion = "V0.1.57"', 1)
write(update, m)

# 4) Invariants.
updater_text = read(updater)
for marker in (
    "function Start-MabiAuto",
    "Starting MABI AUTO through START.cmd.",
    "START.cmd missing; starting release\\FishingAutomation.exe directly.",
    "Start-MabiAuto",
):
    if marker not in updater_text:
        raise SystemExit(f"updater fix marker missing: {marker}")
if old_restart in updater_text:
    raise SystemExit("old unconditional START.cmd restart call remains")
if not start_cmd.is_file():
    raise SystemExit("START.cmd was not created")
if "<Version>0.1.57</Version>" not in read(project):
    raise SystemExit("project version not V0.1.57")
if 'CurrentVersion = "V0.1.57"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.57")

print("V0.1.57 applied: bootstrap START.cmd added and updater restart fallback hardened")
