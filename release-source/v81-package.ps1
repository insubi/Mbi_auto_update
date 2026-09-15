param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'v81-verify.ps1') -SourceRoot $SourceRoot
$baseScript = Join-Path $PSScriptRoot 'v75-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v75 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace("'v75-verify.ps1'","'v81-verify.ps1'")
$text = $text.Replace("Replace('v74','v75')","Replace('v74','v81')")
$text = $text.Replace("Replace('V0.1.1','V0.1.2')","Replace('V0.1.1','V0.1.8')")
$text = $text.Replace("Replace('V0_1_1_ABYSS_CLEAR_GUARD_AUDIT.json','V0_1_2_STABILITY_AUDIT.json')","Replace('V0_1_1_ABYSS_CLEAR_GUARD_AUDIT.json','V0_1_8_REAL_DEBUG_HOOK_AUDIT.json')")
$text = $text.Replace("Replace('0.1.1.0','0.1.2.0')","Replace('0.1.1.0','0.1.8.0')")
$text = $text.Replace("MabiAuto_v75","MabiAuto_v81")
$text = $text.Replace("v75-package-inventory.json","v81-package-inventory.json")
$text = $text.Replace("MabiAuto_v75_Windows_Lite.zip","MabiAuto_v81_Windows_Lite.zip")
$text = $text.Replace("V0.1.2","V0.1.8")
$text = $text.Replace("V0_1_2_STABILITY_AUDIT.json","V0_1_8_REAL_DEBUG_HOOK_AUDIT.json")
$text = $text.Replace("0.1.2.0","0.1.8.0")
$tmp = Join-Path $PSScriptRoot ('mabiauto-v81-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "V0.1.8 package delegate failed: $LASTEXITCODE" }
} finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
$liteRoot = Join-Path $OutputRoot 'MabiAuto_v81'
$sourceHook = Join-Path $liteRoot 'FishingAutomation/templates/hook.png'
$runtimeHook = Join-Path $liteRoot 'release/templates/hook.png'
foreach ($path in @($sourceHook,$runtimeHook)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.8 packaged hook missing: $path" }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne 'b85d3443d156ec31957a7b24ddeeb507a1c5bbbcbf2d3dad4be8213114b4ce8d') { throw "V0.1.8 packaged hook mismatch: $path" }
}
Write-Host 'V0.1.8 PACKAGE VERIFIED: real-debug hook threshold/confirmation fix, narrowed recovery ROI, live capture origin, focus recovery and current hook asset are preserved.'
