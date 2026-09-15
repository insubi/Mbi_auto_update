param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'v80-verify.ps1') -SourceRoot $SourceRoot
$baseScript = Join-Path $PSScriptRoot 'v75-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v75 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace("'v75-verify.ps1'","'v80-verify.ps1'")
$text = $text.Replace("Replace('v74','v75')","Replace('v74','v80')")
$text = $text.Replace("Replace('V0.1.1','V0.1.2')","Replace('V0.1.1','V0.1.7')")
$text = $text.Replace("Replace('V0_1_1_ABYSS_CLEAR_GUARD_AUDIT.json','V0_1_2_STABILITY_AUDIT.json')","Replace('V0_1_1_ABYSS_CLEAR_GUARD_AUDIT.json','V0_1_7_FISHING_CAPTURE_RESYNC_AUDIT.json')")
$text = $text.Replace("Replace('0.1.1.0','0.1.2.0')","Replace('0.1.1.0','0.1.7.0')")
$text = $text.Replace("MabiAuto_v75","MabiAuto_v80")
$text = $text.Replace("v75-package-inventory.json","v80-package-inventory.json")
$text = $text.Replace("MabiAuto_v75_Windows_Lite.zip","MabiAuto_v80_Windows_Lite.zip")
$text = $text.Replace("V0.1.2","V0.1.7")
$text = $text.Replace("V0_1_2_STABILITY_AUDIT.json","V0_1_7_FISHING_CAPTURE_RESYNC_AUDIT.json")
$text = $text.Replace("0.1.2.0","0.1.7.0")
$tmp = Join-Path $PSScriptRoot ('mabiauto-v80-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "V0.1.7 package delegate failed: $LASTEXITCODE" }
} finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
$liteRoot = Join-Path $OutputRoot 'MabiAuto_v80'
$sourceHook = Join-Path $liteRoot 'FishingAutomation/templates/hook.png'
$runtimeHook = Join-Path $liteRoot 'release/templates/hook.png'
foreach ($path in @($sourceHook,$runtimeHook)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.7 packaged hook missing: $path" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne 'b85d3443d156ec31957a7b24ddeeb507a1c5bbbcbf2d3dad4be8213114b4ce8d') { throw "V0.1.7 packaged hook mismatch: $path" }
}
Write-Host 'V0.1.7 PACKAGE VERIFIED: live capture origin refresh, adaptive hook search, forced runtime hook refresh, foreground recovery and current hook asset are preserved.'
