#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: v0137_updater_survival.py SOURCE_ROOT")

root=Path(sys.argv[1]).resolve()
apply=root/"tools"/"ApplyUpdate.ps1"
if not apply.exists():
    raise RuntimeError("tools/ApplyUpdate.ps1 missing in source package")
text=apply.read_text(encoding="utf-8-sig")

old="""    foreach ($name in @('release','FishingAutomation','tools')) {
        Remove-Item -LiteralPath (Join-Path $InstallRoot $name) -Recurse -Force -ErrorAction SilentlyContinue
    }
"""
new="""    # V0.1.37 updater survival: only remove trees that the incoming package actually contains.
    # This prevents a runtime-only package from deleting the local updater/source tree.
    foreach ($name in @('release','FishingAutomation','tools')) {
        $incomingTree = Join-Path $sourceRoot $name
        if (Test-Path -LiteralPath $incomingTree) {
            Remove-Item -LiteralPath (Join-Path $InstallRoot $name) -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
"""
if old not in text:
    raise RuntimeError("normal replacement removal block not found")
text=text.replace(old,new,1)

# Require the incoming package to carry the updater forward.
anchor="""    $incomingExe = Join-Path $sourceRoot 'release\\FishingAutomation.exe'
    if (-not (Test-Path -LiteralPath $incomingExe)) {
        throw '업데이트 패키지에 release\\FishingAutomation.exe가 없습니다. Windows_Lite 패키지를 사용하세요.'
    }
"""
replacement=anchor+"""
    $incomingUpdater = Join-Path $sourceRoot 'tools\\ApplyUpdate.ps1'
    if (-not (Test-Path -LiteralPath $incomingUpdater)) {
        throw '업데이트 패키지에 tools\\ApplyUpdate.ps1가 없습니다. 다음 업데이트가 끊기지 않도록 updater 포함 패키지가 필요합니다.'
    }
"""
if anchor not in text:
    raise RuntimeError("incoming exe validation block not found")
text=text.replace(anchor,replacement,1)

apply.write_text(text,encoding="utf-8",newline="\n")

check=apply.read_text(encoding="utf-8-sig")
for marker in ("V0.1.37 updater survival","$incomingUpdater","tools\\ApplyUpdate.ps1"):
    if marker not in check:
        raise RuntimeError("updater survival marker missing: "+marker)
print("V0.1.37 updater survival patch applied")
