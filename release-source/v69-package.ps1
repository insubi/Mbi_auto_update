param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'v69-verify.ps1') -SourceRoot $SourceRoot

$baseScript = Join-Path $PSScriptRoot 'v66-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v66 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace('v66','v69')
$text = $text.Replace('V66_ABYSS_CLEAR_AUTOSTOP_AUDIT.json','V69_UI_ABYSS_AUDIT.json')
$text = $text.Replace('66.0.0.0','69.0.0.0')
$text = $text.Replace('v69 updates:', 'v69 updates: HOME UI, Telegram dialog, Abyss previews and continuous clear recovery')
$newWatchdogCheck = @'
$watchdog = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ParentProcessId -eq $process.Id -and $_.Name -eq 'MacroWatchdog.exe'
    })
'@
$watchdogPattern = '(?ms)^\s*\$watchdog = @\(Get-Process -Name MacroWatchdog.*?^\s*\}\)'
$text = [regex]::Replace($text, $watchdogPattern, { param($match) "`r`n$newWatchdogCheck" }, 1)
# Confirm that the original path-based block is gone and the parent-PID check exists once.
if ($text.Contains('$watchdog = @(Get-Process -Name MacroWatchdog') -or
    ([regex]::Matches($text, [regex]::Escape('$watchdog = @(Get-CimInstance Win32_Process'))).Count -ne 1) {
    throw 'Base Watchdog verification block changed'
}

$tmp = Join-Path $env:TEMP ('mabiauto-v69-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "v69 package delegate failed: $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}

$liteRoot = Join-Path $OutputRoot 'MabiAuto_v69'
foreach ($rel in @(
    'release/abyss/templates/hallucination_anchorage.png',
    'release/abyss/templates/madness_cave.png',
    'release/abyss/templates/scattered_waterway.png',
    'FishingAutomation/abyss/templates/hallucination_anchorage.png',
    'FishingAutomation/abyss/templates/madness_cave.png',
    'FishingAutomation/abyss/templates/scattered_waterway.png',
    'tools/ApplyUpdate.ps1','release/MacroWatchdog.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $liteRoot $rel))) { throw "v69 package path missing: $rel" }
}
Write-Host 'V69 PACKAGE VERIFIED: all Abyss previews and updater/Watchdog paths included.'
