param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
# Never clean a checkout or an existing installation. Each build gets a new folder.
if (Test-Path -LiteralPath $OutputRoot) { throw "Output must not exist: $OutputRoot" }
New-Item -ItemType Directory -Path $OutputRoot | Out-Null
$audit = Get-Content -LiteralPath (Join-Path $SourceRoot 'V58_PACKAGING_AUDIT.json') -Raw | ConvertFrom-Json
if ($audit.version -ne 'v58') { throw 'Expected audited v58 source' }
$app = Join-Path $SourceRoot 'FishingAutomation'
foreach ($entry in $audit.protected_sha256.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $SourceRoot $entry.Name) -Algorithm SHA256).Hash -ne $entry.Value) {
        throw "Source integrity mismatch: $($entry.Name)"
    }
}
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

$liteRoot = Join-Path $OutputRoot 'MabiAuto_v58'
$runtime = Join-Path $liteRoot 'release'
$mirror = Join-Path $liteRoot 'FishingAutomation'
New-Item -ItemType Directory -Path $runtime,$mirror | Out-Null
Copy-Item -Path (Join-Path $publishMain '*') -Destination $runtime -Recurse
# Publish output is authoritative for framework/native dependencies. Do not trim it.
Copy-Item -LiteralPath (Join-Path $publishWatch 'MacroWatchdog.exe') -Destination $runtime
# .NET bundles this native DLL. Keep the explicit path used by InputSender and
# by the existing driver's install/update preservation contract as well.
Copy-Item -LiteralPath (Join-Path $app 'interception.dll') -Destination $runtime -Force
$assets = @($audit.runtime_assets.PSObject.Properties)
foreach ($entry in $assets) {
    $src = Join-Path $app $entry.Name
    $published = Join-Path $runtime $entry.Name
    if (-not (Test-Path -LiteralPath $published) -or
        (Get-FileHash -LiteralPath $published -Algorithm SHA256).Hash -ne $entry.Value) {
        throw "Publish omitted or changed runtime asset: $($entry.Name)"
    }
    $dst = Join-Path $mirror $entry.Name
    New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst
}
# These mirrors are used by UI previews, diagnostics, settings tools and updater.
# The installer downloads the official driver; only its x64 runtime DLL is shipped.
$rootFiles = @('1_INSTALL_INTERCEPTION.cmd','SETUP_PHONE_ALERT.cmd','SETUP_PHONE_ALERT_ALT.bat',
    'ADD_TEMPLATES.cmd','OPEN_TEMPLATES.cmd','PHONE_ALERT_README.txt','AUTO_UPDATE_README.txt','RUN_DIAGNOSTIC.cmd')
$toolFiles = @('InstallInterception.ps1','SetupPhoneAlert.ps1','AddTemplates.ps1','ApplyUpdate.ps1')
New-Item -ItemType Directory -Path (Join-Path $liteRoot 'tools') | Out-Null
foreach ($rel in @($rootFiles) + @($toolFiles | ForEach-Object { "tools/$_" })) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $rel) -Destination (Join-Path $liteRoot $rel)
    if ((Get-FileHash -LiteralPath (Join-Path $SourceRoot $rel)).Hash -ne
        (Get-FileHash -LiteralPath (Join-Path $liteRoot $rel)).Hash) { throw "Tool changed: $rel" }
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
MABI AUTO v58 - Windows Lite

Extract this ZIP completely, then run START.cmd.
.NET SDK/runtime installation is not required (self-contained Windows x64).
If Interception is not installed, run 1_INSTALL_INTERCEPTION.cmd and reboot.
For phone alerts, run SETUP_PHONE_ALERT.cmd.

v58 changes packaging only; v57 gameplay, OCR and update recovery are preserved.
Settings/template copies in release and FishingAutomation are required by existing tools.
No .NET/OpenCV/OCR/WinForms trimming or native dependency removal is used.
'@ | Set-Content -LiteralPath (Join-Path $liteRoot 'WINDOWS_LITE.txt') -Encoding UTF8

# Check all package paths, not just top-level files. Unknown publish content fails
# the build instead of silently dropping a possibly required native dependency.
$runtimeNames = @($assets.Name) + @('FishingAutomation.exe','MacroWatchdog.exe')
foreach ($file in Get-ChildItem -LiteralPath $liteRoot -Recurse -File) {
    $rel = [IO.Path]::GetRelativePath($liteRoot, $file.FullName).Replace('\','/')
    $allowed = $false
    if ($rel.StartsWith('release/')) {
        $sub = $rel.Substring(8)
        $allowed = $sub -in $runtimeNames -or $sub -match '^[^/]+\.dll$' -or
            $sub -match '^FishingAutomation\.(deps|runtimeconfig)\.json$' -or
            $sub -match '^[a-z]{2}(-[A-Za-z]+)?/[^/]+\.resources\.dll$'
    } elseif ($rel.StartsWith('FishingAutomation/')) {
        $allowed = $rel.Substring(18) -in $assets.Name
    } else {
        $allowed = $rel -in $rootFiles -or $rel -in @('START.cmd','WINDOWS_LITE.txt') -or
            $rel -in @($toolFiles | ForEach-Object { "tools/$_" })
    }
    if (-not $allowed) { throw "Unexpected distribution file: $rel" }
}
$version = (Get-Item -LiteralPath (Join-Path $runtime 'FishingAutomation.exe')).VersionInfo.FileVersion
if ($version -ne '58.0.0.0') { throw "Unexpected executable version: $version" }

# Test a disposable copy. Do not alter shipped settings or send phone alerts.
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
    Write-Host 'STARTUP HEALTH OK: WinForms app and Watchdog started from packaged paths.'
} finally {
    foreach ($name in @('FishingAutomation','MacroWatchdog')) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -and $_.Path.StartsWith($smoke + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
        } | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

$zip = Join-Path $OutputRoot 'MabiAuto_v58_Windows_Lite.zip'
Compress-Archive -LiteralPath $liteRoot -DestinationPath $zip -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  MabiAuto_v58_Windows_Lite.zip" | Set-Content -LiteralPath "$zip.sha256" -Encoding ASCII
$inventory = @(Get-ChildItem -LiteralPath $liteRoot -Recurse -File | ForEach-Object {
    [ordered]@{ path = [IO.Path]::GetRelativePath($liteRoot, $_.FullName).Replace('\','/');
        bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$inventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputRoot 'v58-package-inventory.json') -Encoding UTF8
Write-Host "WINDOWS LITE VERIFIED: $($inventory.Count) files; $((Get-Item $zip).Length) bytes; SHA256 $hash"
