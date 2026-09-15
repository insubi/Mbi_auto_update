param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'v72-verify.ps1') -SourceRoot $SourceRoot

$baseScript = Join-Path $PSScriptRoot 'v66-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v66 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace('v66','v72')
$text = $text.Replace('V66_ABYSS_CLEAR_AUTOSTOP_AUDIT.json','V72_SCENIC_PREVIEW_AUDIT.json')
$text = $text.Replace('66.0.0.0','72.0.0.0')
$text = $text.Replace('v72 updates:', 'v72 updates: scenic Abyss card previews separated from recognition templates; v71 HOME polish preserved')

$newWatchdogCheck = @'
$watchdog = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ParentProcessId -eq $process.Id -and $_.Name -eq 'MacroWatchdog.exe'
    })
'@
$watchdogPattern = '(?ms)^\s*\$watchdog = @\(Get-Process -Name MacroWatchdog.*?^\s*\}\)'
$text = [regex]::Replace($text, $watchdogPattern, { param($match) "`r`n$newWatchdogCheck" }, 1)
if ($text.Contains('$watchdog = @(Get-Process -Name MacroWatchdog') -or
    ([regex]::Matches($text, [regex]::Escape('$watchdog = @(Get-CimInstance Win32_Process'))).Count -ne 1) {
    throw 'Base Watchdog verification block changed'
}

$tmp = Join-Path $env:TEMP ('mabiauto-v72-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "v72 package delegate failed: $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}

$liteRoot = Join-Path $OutputRoot 'MabiAuto_v72'
$previewSource = Join-Path $SourceRoot 'FishingAutomation/abyss/previews'
foreach ($destBase in @(
    (Join-Path $liteRoot 'release/abyss/previews'),
    (Join-Path $liteRoot 'FishingAutomation/abyss/previews'))) {
    New-Item -ItemType Directory -Path $destBase -Force | Out-Null
    foreach ($name in @('hallucination_anchorage.jpg','madness_cave.jpg','scattered_waterway.jpg')) {
        Copy-Item -LiteralPath (Join-Path $previewSource $name) -Destination (Join-Path $destBase $name) -Force
    }
}

$expected = @{
    'hallucination_anchorage.jpg' = '0195c292d2b32cb369d2561ab01227e4b7120e9cade8178cc174d40bf8ceeb9d'
    'madness_cave.jpg' = 'e6af39c665f1126dde46f17054589413b88690a0eaae56fc14e06a6434b4e50e'
    'scattered_waterway.jpg' = 'd1d56c996e21aaf60c8ec6d09770b2b93ae918ea1c1c290f4e767b62490c1ff6'
}
foreach ($destBase in @(
    (Join-Path $liteRoot 'release/abyss/previews'),
    (Join-Path $liteRoot 'FishingAutomation/abyss/previews'))) {
    foreach ($entry in $expected.GetEnumerator()) {
        $path = Join-Path $destBase $entry.Key
        if (-not (Test-Path -LiteralPath $path)) { throw "v72 preview package path missing: $path" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
            throw "v72 preview package hash mismatch: $path"
        }
    }
}

# Rebuild the ZIP/inventory after adding preview-only assets because the delegated
# v66 packager creates its archive before this v72-specific copy step.
$zip = Join-Path $OutputRoot 'MabiAuto_v72_Windows_Lite.zip'
Remove-Item -LiteralPath $zip,"$zip.sha256" -Force -ErrorAction SilentlyContinue
Compress-Archive -LiteralPath $liteRoot -DestinationPath $zip -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  MabiAuto_v72_Windows_Lite.zip" | Set-Content -LiteralPath "$zip.sha256" -Encoding ASCII
$inventory = @(Get-ChildItem -LiteralPath $liteRoot -Recurse -File | ForEach-Object {
    [ordered]@{ path = [IO.Path]::GetRelativePath($liteRoot, $_.FullName).Replace('\','/');
        bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$inventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputRoot 'v72-package-inventory.json') -Encoding UTF8
Write-Host "V72 PACKAGE VERIFIED: scenic previews included separately from recognition templates; SHA256 $hash"
