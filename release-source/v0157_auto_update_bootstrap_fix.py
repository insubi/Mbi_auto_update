#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
app = root / "FishingAutomation"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")

# 1) Restore a package-root bootstrap launcher.
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
    encoding="ascii"
)

# 2) Add an ASCII-only one-time repair bridge for already-installed V0.1.55/56.
# Those builds can have a BOM-less UTF-8 ApplyUpdate.ps1; Windows PowerShell 5.1
# may parse its Korean strings as ANSI and fail before it can extract a new ZIP.
repair_cmd = root / "REPAIR_AUTO_UPDATE.cmd"
repair_cmd.write_text(
    '@echo off\r\n'
    'setlocal\r\n'
    'cd /d "%~dp0"\r\n'
    'set "LOG=%~dp0auto_update_repair.log"\r\n'
    'echo [MABI AUTO] Repair started.>"%LOG%"\r\n'
    'if not exist "%~dp0tools\\ApplyUpdate.ps1" (\r\n'
    '  echo ERROR: tools\\ApplyUpdate.ps1 not found.>>"%LOG%"\r\n'
    '  echo [MABI AUTO] tools\\ApplyUpdate.ps1 not found.\r\n'
    '  exit /b 1\r\n'
    ')\r\n'
    'if not exist "%~dp0release\\FishingAutomation.exe" (\r\n'
    '  echo ERROR: release\\FishingAutomation.exe not found.>>"%LOG%"\r\n'
    '  echo [MABI AUTO] release\\FishingAutomation.exe not found.\r\n'
    '  exit /b 1\r\n'
    ')\r\n'
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p=[IO.Path]::GetFullPath(\'tools\\ApplyUpdate.ps1\');$s=[IO.File]::ReadAllText($p,[Text.Encoding]::UTF8);$enc=New-Object System.Text.UTF8Encoding -ArgumentList $true;[IO.File]::WriteAllText($p,$s,$enc)"\r\n'
    'if errorlevel 1 (\r\n'
    '  echo ERROR: updater encoding repair failed.>>"%LOG%"\r\n'
    '  echo [MABI AUTO] updater encoding repair failed.\r\n'
    '  exit /b 1\r\n'
    ')\r\n'
    '> "%~dp0START.cmd" echo @echo off\r\n'
    '>>"%~dp0START.cmd" echo setlocal\r\n'
    '>>"%~dp0START.cmd" echo cd /d "%%~dp0"\r\n'
    '>>"%~dp0START.cmd" echo start "" "%%~dp0release\\FishingAutomation.exe"\r\n'
    '>>"%~dp0START.cmd" echo exit /b 0\r\n'
    'echo OK: updater UTF-8 BOM and START.cmd repaired.>>"%LOG%"\r\n'
    'echo [MABI AUTO] Auto-update repair complete.\r\n'
    'echo Close this window, then start MABI AUTO again.\r\n'
    'exit /b 0\r\n',
    encoding="ascii"
)

# 3) Harden the updater used by V0.1.57 and later.
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

    $exe = Join-Path $InstallRoot 'release\\FishingAutomation.exe'
    if (Test-Path -LiteralPath $exe) {
        Log 'START.cmd missing; starting release\\FishingAutomation.exe directly.'
        Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe -Parent)
        return
    }

    throw '업데이트 후 실행 파일을 찾지 못했습니다. START.cmd와 release\\FishingAutomation.exe가 모두 없습니다.'
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

# Windows PowerShell 5.1 must see a UTF-8 BOM because this script contains Korean text.
updater.write_text(u, encoding="utf-8-sig", newline="\r\n")

# 4) Metadata-only version bump.
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

# 5) Invariants.
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
if not repair_cmd.is_file():
    raise SystemExit("REPAIR_AUTO_UPDATE.cmd was not created")
if updater.read_bytes()[:3] != b"\xef\xbb\xbf":
    raise SystemExit("ApplyUpdate.ps1 is not UTF-8 BOM encoded")
if "<Version>0.1.57</Version>" not in read(project):
    raise SystemExit("project version not V0.1.57")
if 'CurrentVersion = "V0.1.57"' not in read(update):
    raise SystemExit("UpdateManager version not V0.1.57")

print("V0.1.57 applied: START bootstrap, PowerShell BOM, updater fallback, and one-time repair bridge")
