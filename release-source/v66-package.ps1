param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'

$baseScript = Join-Path $PSScriptRoot 'v65-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v65 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace('v65','v66')
$text = $text.Replace('V65_ABYSS_POPUP_AUDIT.json','V66_ABYSS_CLEAR_AUTOSTOP_AUDIT.json')
$text = $text.Replace('65.0.0.0','66.0.0.0')

$pattern = "(?s)@'\r?\nMABI AUTO v66 - Windows Lite.*?'@\s*\|\s*Set-Content -LiteralPath \(Join-Path \$liteRoot 'WINDOWS_LITE.txt'\) -Encoding UTF8"
$replacement = @'
@'
MABI AUTO v66 - Windows Lite

v66 updates:
- Home dashboard only: compact auto-stop control above System Status; other windows/layouts unchanged
- Auto-stop uses the same safe stop path as F10 and persists the selected time
- Abyss clear detection is image-only multi-scale: dungeon-clear visual OR touch-screen visual
- Clear requires two consecutive valid image detections; rank S and OCR are not used for clear detection
- v65 popup-close template-only guard is retained
- Existing scene-skip, treasure chest, recovery, retry, administrator elevation and exact 800x1000 handling are retained
'@ | Set-Content -LiteralPath (Join-Path $liteRoot 'WINDOWS_LITE.txt') -Encoding UTF8
'@
$text = [regex]::Replace($text, $pattern, $replacement, 1)

$tmp = Join-Path $env:TEMP ('mabiauto-v66-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "v66 package delegate failed: $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
