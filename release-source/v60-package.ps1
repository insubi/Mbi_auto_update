param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $OutputRoot) { throw "Output must not exist: $OutputRoot" }
New-Item -ItemType Directory -Path $OutputRoot | Out-Null

$v60AuditPath = Join-Path $SourceRoot 'V60_DUAL_MONITOR_AUDIT.json'
if (-not (Test-Path -LiteralPath $v60AuditPath)) { throw 'V60 dual-monitor audit missing' }
$v60Audit = Get-Content -LiteralPath $v60AuditPath -Raw | ConvertFrom-Json
if ($v60Audit.version -ne 'v60') { throw 'Expected audited v60 source' }
foreach ($entry in $v60Audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Audited v60 file missing: $($entry.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.ToLowerInvariant()) {
        throw "v60 source integrity mismatch: $($entry.Name)"
    }
}

$v58AuditPath = Join-Path $SourceRoot 'V58_PACKAGING_AUDIT.json'
if (-not (Test-Path -LiteralPath $v58AuditPath)) { throw 'V58 packaging audit missing from v60 base source' }
$v58Audit = Get-Content -LiteralPath $v58AuditPath -Raw | ConvertFrom-Json
$app = Join-Path $SourceRoot 'FishingAutomation'

$publishMain = Join-Path $OutputRoot 'publish-main'
$publishWatch = Join-Path $OutputRoot 'publish-watchdog'
$publishArgs = @('-c','Release','-r','win-x64','--self-contained','true',
    '-p:PublishSingleFile=true','-p:IncludeNativeLibrariesForSelfExtract=true',
    '-p:EnableCompressionInSingleFile=true','-p:PublishTrimmed=false','-p:PublishAot=false',
    '-p:DebugType=None','-p:DebugSymbols=false')

dotnet publish (Join-Path $app 'FishingAutomation.csproj') @publishArgs -o $publishMain
if ($LASTEXITCODE -ne 0) { throw 'Main publish failed' }
dotnet publish (Join-Path $SourceRoot 'MacroWatchdog/MacroWatchdog.csproj') @publishArgs -o $publishWatch
if ($LASTEXITCODE -ne 0) { throw 'Watchdog publish failed' }

$liteRoot = Join-Path $OutputRoot 'MabiAuto_v60'
$runtime = Join-Path $liteRoot 'release'
$mirror = Join-Path $liteRoot 'FishingAutomation'
New-Item -ItemType Directory -Path $runtime,$mirror | Out-Null
Copy-Item -Path (Join-Path $publishMain '*') -Destination $runtime -Recurse
Copy-Item -LiteralPath (Join-Path $publishWatch 'MacroWatchdog.exe') -Destination $runtime
Copy-Item -LiteralPath (Join-Path $app 'interception.dll') -Destination $runtime -Force

$assets = @($v58Audit.runtime_assets.PSObject.Properties)
foreach ($entry in $assets) {
    $src = Join-Path $app $entry.Name
    if (-not (Test-Path -LiteralPath $src)) { throw "Runtime asset missing: $($entry.Name)" }
    $published = Join-Path $runtime $entry.Name
    if (-not (Test-Path -LiteralPath $published)) { throw "Publish omitted runtime asset: $($entry.Name)" }
    $dst = Join-Path $mirror $entry.Name
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
}

$rootFiles = @('1_INSTALL_INTERCEPTION.cmd','SETUP_PHONE_ALERT.cmd','SETUP_PHONE_ALERT_ALT.bat',
    'ADD_TEMPLATES.cmd','OPEN_TEMPLATES.cmd','PHONE_ALERT_README.txt','AUTO_UPDATE_README.txt','RUN_DIAGNOSTIC.cmd')
$toolFiles = @('InstallInterception.ps1','SetupPhoneAlert.ps1','AddTemplates.ps1','ApplyUpdate.ps1')
New-Item -ItemType Directory -Path (Join-Path $liteRoot 'tools') | Out-Null
foreach ($rel in @($rootFiles) + @($toolFiles | ForEach-Object { "tools/$_" })) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $rel) -Destination (Join-Path $liteRoot $rel)
}

@'
@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "EXE=%~dp0release\FishingAutomation.exe"
if not exist "%EXE%" (
  echo.
  echo ERROR: release\FishingAutomation.exe is missing.
  echo Download the Windows_Lite ZIP again and extract all files.
  echo.
  pause
  exit /b 6
)
start "" /d "%~dp0release" "%EXE%"
exit /b 0
'@ | Set-Content -LiteralPath (Join-Path $liteRoot 'START.cmd') -Encoding ASCII

@'
MABI AUTO v60 - Windows Lite

Extract this ZIP completely, then run START.cmd.
.NET SDK/runtime installation is not required (self-contained Windows x64).
If Interception is not installed, run 1_INSTALL_INTERCEPTION.cmd and reboot.
For phone alerts, run SETUP_PHONE_ALERT.cmd.

v60 dual-monitor placement correction:
- actual game client area remains 800x1000
- macro start always targets the PRIMARY monitor working area's top-right corner
- repeated measured-client correction from v59 is retained
- Fishing, Dungeon and Abyss use the same primary-monitor placement rule
v58 packaging and v57 updater/watchdog recovery remain intact.
'@ | Set-Content -LiteralPath (Join-Path $liteRoot 'WINDOWS_LITE.txt') -Encoding UTF8

$version = (Get-Item -LiteralPath (Join-Path $runtime 'FishingAutomation.exe')).VersionInfo.FileVersion
if ($version -ne '60.0.0.0') { throw "Unexpected executable version: $version" }

$smoke = Join-Path $OutputRoot 'smoke'
Copy-Item -LiteralPath $liteRoot -Destination $smoke -Recurse
foreach ($dir in @('release','FishingAutomation')) {
    '{"Enabled":false,"RemoteControlEnabled":false,"BotToken":"","ChatId":""}' |
        Set-Content -LiteralPath (Join-Path $smoke "$dir/notification.json") -Encoding UTF8
}
$token = [Guid]::NewGuid().ToString('N')
Set-Content -LiteralPath (Join-Path $smoke '.update_pending') -Value $token -Encoding ASCII
$exe = Join-Path $smoke 'release/FishingAutomation.exe'
try {
    $process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe -Parent) -WindowStyle Hidden -PassThru
    $healthy = Join-Path $smoke '.update_healthy'
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $process.Refresh()
        if ($process.HasExited) { throw "Startup exited: $($process.ExitCode)" }
        if ((Test-Path -LiteralPath $healthy) -and (Get-Content -LiteralPath $healthy -Raw).Trim() -eq $token) {
            $ok = $true; break
        }
    }
    if (-not $ok) { throw 'Startup health marker was not written' }
    $watchdog = @(Get-Process -Name MacroWatchdog -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -eq (Join-Path $smoke 'release/MacroWatchdog.exe')
    })
    if ($watchdog.Count -ne 1) { throw 'Watchdog did not start alongside the app' }
    Write-Host 'STARTUP HEALTH OK: v60 WinForms app and Watchdog started.'
} finally {
    foreach ($name in @('FishingAutomation','MacroWatchdog')) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -and $_.Path.StartsWith($smoke + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
        } | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

$zip = Join-Path $OutputRoot 'MabiAuto_v60_Windows_Lite.zip'
Compress-Archive -LiteralPath $liteRoot -DestinationPath $zip -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  MabiAuto_v60_Windows_Lite.zip" | Set-Content -LiteralPath "$zip.sha256" -Encoding ASCII
$inventory = @(Get-ChildItem -LiteralPath $liteRoot -Recurse -File | ForEach-Object {
    [ordered]@{ path = [IO.Path]::GetRelativePath($liteRoot, $_.FullName).Replace('\','/');
        bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$inventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputRoot 'v60-package-inventory.json') -Encoding UTF8
Write-Host "WINDOWS LITE VERIFIED: $($inventory.Count) files; $((Get-Item $zip).Length) bytes; SHA256 $hash"
