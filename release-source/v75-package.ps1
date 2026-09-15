param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'v75-verify.ps1') -SourceRoot $SourceRoot

# Reuse the proven V0.1.1/v74 packaging path, changing only version/audit identifiers.
$baseScript = Join-Path $PSScriptRoot 'v74-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v74 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace('v74','v75')
$text = $text.Replace('V0.1.1','V0.1.2')
$text = $text.Replace('V0_1_1_ABYSS_CLEAR_GUARD_AUDIT.json','V0_1_2_STABILITY_AUDIT.json')
$text = $text.Replace('0.1.1.0','0.1.2.0')
$text = $text.Replace('Abyss false-clear guard requires clear-title + touch-prompt together for 3 consecutive frames',
    'Abyss stability: BOTH images in one frame then immediate touch; Home+End+K+I outside HUD confirmation; verified exit; repaired monitors')

$tmp = Join-Path $env:TEMP ('mabiauto-v75-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "V0.1.2 package delegate failed: $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}

$liteRoot = Join-Path $OutputRoot 'MabiAuto_v75'
if (-not (Test-Path -LiteralPath $liteRoot)) { throw 'V0.1.2 lite root missing after delegated package build' }

# Verify repaired monitors and fixed-HUD outside templates in runtime and mirrored source paths.
Add-Type -AssemblyName System.Drawing
$requiredImages = @(
    'release/abyss/templates/popup_close.png',
    'release/abyss/templates/scene_skip_phone.jpg',
    'release/dungeon/templates/scene_skip_phone.jpg',
    'release/abyss/templates/outside_home_v75.png',
    'release/abyss/templates/outside_end_v75.png',
    'release/abyss/templates/outside_k_v75.png',
    'release/abyss/templates/outside_i_v75.png',
    'FishingAutomation/abyss/templates/popup_close.png',
    'FishingAutomation/abyss/templates/scene_skip_phone.jpg',
    'FishingAutomation/dungeon/templates/scene_skip_phone.jpg',
    'FishingAutomation/abyss/templates/outside_home_v75.png',
    'FishingAutomation/abyss/templates/outside_end_v75.png',
    'FishingAutomation/abyss/templates/outside_k_v75.png',
    'FishingAutomation/abyss/templates/outside_i_v75.png'
)
foreach ($rel in $requiredImages) {
    $path = Join-Path $liteRoot $rel
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.2 runtime image missing: $rel" }
    $img = $null
    try {
        $img = [System.Drawing.Image]::FromFile($path)
        if ($img.Width -lt 2 -or $img.Height -lt 2) { throw "Invalid dimensions $($img.Width)x$($img.Height)" }
    } catch {
        throw "V0.1.2 packaged image decode failed: ${rel}: $($_.Exception.Message)"
    } finally { if ($null -ne $img) { $img.Dispose() } }
}

$zip = Join-Path $OutputRoot 'MabiAuto_v75_Windows_Lite.zip'
Remove-Item -LiteralPath $zip,"$zip.sha256" -Force -ErrorAction SilentlyContinue
Compress-Archive -LiteralPath $liteRoot -DestinationPath $zip -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  MabiAuto_v75_Windows_Lite.zip" | Set-Content -LiteralPath "$zip.sha256" -Encoding ASCII
$inventory = @(Get-ChildItem -LiteralPath $liteRoot -Recurse -File | ForEach-Object {
    [ordered]@{ path = [IO.Path]::GetRelativePath($liteRoot, $_.FullName).Replace('\','/'); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$inventory | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputRoot 'v75-package-inventory.json') -Encoding UTF8
Write-Host "V0.1.2 PACKAGE VERIFIED (legacy bridge v75): $($inventory.Count) files; SHA256 $hash"
