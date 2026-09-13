param([Parameter(Mandatory=$true)][string]$PackageRoot)
$ErrorActionPreference = 'Stop'
$appDir = Join-Path $PackageRoot 'FishingAutomation'

dotnet publish (Join-Path $appDir 'FishingAutomation.csproj') -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true -p:DebugType=None -p:DebugSymbols=false -o publish-main
if ($LASTEXITCODE -ne 0) { throw 'Windows main app publish failed' }
dotnet publish (Join-Path $PackageRoot 'MacroWatchdog/MacroWatchdog.csproj') -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true -p:DebugType=None -p:DebugSymbols=false -o publish-watchdog
if ($LASTEXITCODE -ne 0) { throw 'Windows Watchdog publish failed' }

$lite = Join-Path $PWD 'lite/MabiAuto_v33'
$runtime = Join-Path $lite 'release'
$mini = Join-Path $lite 'FishingAutomation'
New-Item -ItemType Directory -Force -Path $runtime,$mini,(Join-Path $lite 'tools') | Out-Null
Copy-Item publish-main/* $runtime -Recurse -Force
Copy-Item publish-watchdog/MacroWatchdog.exe (Join-Path $runtime 'MacroWatchdog.exe') -Force
foreach ($file in @('config.json','notification.json','interception.dll')) {
  $source = Join-Path $appDir $file
  if (Test-Path $source) { Copy-Item $source (Join-Path $mini $file) }
}
foreach ($folder in @('templates','dungeon','abyss','life','drivers')) {
  $source = Join-Path $appDir $folder
  if (Test-Path $source) { Copy-Item $source (Join-Path $mini $folder) -Recurse -Force }
}
foreach ($tool in @('InstallInterception.ps1','SetupPhoneAlert.ps1','AddTemplates.ps1','ApplyUpdate.ps1')) {
  Copy-Item (Join-Path $PackageRoot "tools/$tool") (Join-Path $lite "tools/$tool")
}
foreach ($file in @('1_INSTALL_INTERCEPTION.cmd','SETUP_PHONE_ALERT.cmd','SETUP_PHONE_ALERT_ALT.bat','ADD_TEMPLATES.cmd','OPEN_TEMPLATES.cmd','PHONE_ALERT_README.txt','AUTO_UPDATE_README.txt','RUN_DIAGNOSTIC.cmd','START_HERE_v33.txt')) {
  Copy-Item (Join-Path $PackageRoot $file) (Join-Path $lite $file)
}
# Only packaging: v32's case-insensitive Dungeon/dungeon content glob can copy
# source files on Windows. Keep source and build directories out of the Lite ZIP.
Get-ChildItem $lite -Recurse -File | Where-Object { $_.Extension -in @('.cs','.csproj','.pdb') } | Remove-Item -Force
Get-ChildItem $lite -Recurse -Directory | Where-Object { $_.Name -in @('bin','obj') } | Sort-Object { $_.FullName.Length } -Descending | Remove-Item -Recurse -Force
$start = @('@echo off','setlocal EnableExtensions','cd /d "%~dp0"','if not exist "%~dp0release\FishingAutomation.exe" exit /b 6','start "" /d "%~dp0release" "%~dp0release\FishingAutomation.exe"','exit /b 0')
Set-Content -LiteralPath (Join-Path $lite 'START.cmd') -Value $start -Encoding ASCII
Set-Content -LiteralPath (Join-Path $lite 'WINDOWS_LITE.txt') -Encoding UTF8 -Value @(
  'MABI AUTO v33 Windows Lite - preview',
  'Main app and Watchdog are self-contained Windows x64 executables. No .NET SDK is required.',
  'Life images have not been supplied. Life startup is blocked until its profile is calibrated.',
  'No real game GUI, keyboard, mouse, Telegram delivery or update/rollback integration was tested.',
  'Read START_HERE_v33.txt before use.'
)
foreach ($name in @('FishingAutomation.exe','MacroWatchdog.exe')) {
  $file = Join-Path $runtime $name
  if (-not (Test-Path $file)) { throw "Missing executable: $name" }
  $bytes = [System.IO.File]::ReadAllBytes($file)
  if ($bytes.Length -lt 1000000 -or $bytes[0] -ne 77 -or $bytes[1] -ne 90) { throw "Invalid PE executable: $name" }
}
if ([System.Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $runtime 'FishingAutomation.exe')).FileVersion -ne '33.0.0.0') { throw 'Wrong app version' }
if (-not (Test-Path (Join-Path $runtime 'life/profile.json'))) { throw 'Life profile absent from published runtime' }
if (Get-ChildItem $lite -Recurse -File | Where-Object { $_.Extension -in @('.cs','.csproj','.pdb') }) { throw 'Source/debug files remain in Lite' }
if (Test-Path (Join-Path $runtime 'life/settings.json')) { throw 'Test or personal life settings leaked into package' }
foreach ($notification in @((Join-Path $runtime 'notification.json'),(Join-Path $mini 'notification.json'))) {
  $config = Get-Content $notification -Raw | ConvertFrom-Json
  if ($config.BotToken -or $config.ChatId) { throw 'Personal Telegram settings must not be packaged' }
}
$name = 'MabiAuto_v33_Windows_Lite_Preview.zip'
Compress-Archive -Path $lite -DestinationPath $name -CompressionLevel Optimal
$hash = (Get-FileHash $name -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $name" | Set-Content "$name.sha256" -Encoding ASCII
@(
  "Commit: $env:GITHUB_SHA",
  "Runner: $env:RUNNER_OS",
  "Source baseline: v32 / SHA256 verified",
  "App: 33.0.0.0 / win-x64 / self-contained / publish succeeded",
  "Watchdog: win-x64 / self-contained / publish succeeded",
  "Rules and Windows UI smoke checks: succeeded in prerequisite step",
  "Life image calibration: pending user screenshots; startup blocked",
  "Game GUI clicks, live OCR accuracy, Interception, Telegram delivery, updater rollback: not tested",
  "SHA256: $hash"
) | Set-Content windows-build-evidence.txt -Encoding UTF8
Write-Host "WINDOWS LITE BUILD OK: $name"
