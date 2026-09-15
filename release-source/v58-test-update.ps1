param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [Parameter(Mandatory=$true)][string]$WorkRoot
)
$ErrorActionPreference = 'Stop'
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
if (Test-Path -LiteralPath $WorkRoot) { throw 'Updater test requires a new isolated directory' }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
$install = Join-Path $WorkRoot 'install'
$incoming = Join-Path $WorkRoot 'incoming'
Copy-Item -LiteralPath $PackageRoot -Destination $install -Recurse
Copy-Item -LiteralPath $PackageRoot -Destination $incoming -Recurse
# Exercise the preserved updater with the package layout. The launcher only returns
# its health token; gameplay and phone notifications are never started here.
$launcher = @'
@echo off
powershell.exe -NoProfile -Command "$root='%~dp0'; Get-Content -LiteralPath ($root + '.update_pending') | Set-Content -LiteralPath ($root + '.update_healthy') -Encoding ASCII"
'@
$launcher | Set-Content -LiteralPath (Join-Path $incoming 'START.cmd') -Encoding ASCII
$preserved = @(
    'FishingAutomation/notification.json','FishingAutomation/config.json','FishingAutomation/interception.dll',
    'FishingAutomation/templates/custom-user.png','FishingAutomation/abyss/templates/custom-user.png',
    'FishingAutomation/dungeon/templates/custom-user.png',
    'release/notification.json','release/config.json','release/interception.dll',
    'release/templates/custom-user.png','release/abyss/templates/custom-user.png','release/dungeon/templates/custom-user.png'
)
$expected = @{}
foreach ($rel in $preserved) {
    $value = if ($rel.EndsWith('notification.json')) { 'notification-user-sentinel' } else { "user-sentinel:$rel" }
    $file = Join-Path $install $rel
    Set-Content -LiteralPath $file -Value $value -Encoding ASCII
    $expected[$rel] = (Get-FileHash -LiteralPath $file).Hash
}
Set-Content -LiteralPath (Join-Path $install 'release/old-debug.pdb') -Value 'obsolete'
$zip = Join-Path $WorkRoot 'incoming.zip'
Compress-Archive -LiteralPath $incoming -DestinationPath $zip
$script = Join-Path $WorkRoot 'ApplyUpdate.ps1'
Copy-Item -LiteralPath (Join-Path $SourceRoot 'tools/ApplyUpdate.ps1') -Destination $script
& $script -ZipPath $zip -InstallRoot $install -ProcessId 2147483647
$log = Get-Content -LiteralPath (Join-Path $install 'update.log') -Raw
if ($log -notmatch 'Update committed\.') { throw 'Updater did not commit the fixture update' }
foreach ($rel in $preserved) {
    if ((Get-FileHash -LiteralPath (Join-Path $install $rel)).Hash -ne $expected[$rel]) {
        throw "Updater lost user data: $rel"
    }
}
foreach ($rel in @('release/FishingAutomation.exe','release/MacroWatchdog.exe','tools/ApplyUpdate.ps1')) {
    if ((Get-FileHash -LiteralPath (Join-Path $install $rel)).Hash -ne
        (Get-FileHash -LiteralPath (Join-Path $PackageRoot $rel)).Hash) { throw "Update path mismatch: $rel" }
}
foreach ($rel in @('release/old-debug.pdb','.update_pending','.update_healthy','.update_rollback')) {
    if (Test-Path -LiteralPath (Join-Path $install $rel)) { throw "Update left stale state: $rel" }
}
'PASS: preserved updater installed the current package layout; 12 user data paths preserved; updater/watchdog paths intact; obsolete PDB removed.' |
    Set-Content -LiteralPath (Join-Path $WorkRoot 'verification.txt') -Encoding UTF8
Get-Content -LiteralPath (Join-Path $WorkRoot 'verification.txt')
