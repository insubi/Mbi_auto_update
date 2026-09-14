param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'

$baseScript = Join-Path $PSScriptRoot 'v66-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v66 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace('v66','v67')
$text = $text.Replace('V66_ABYSS_CLEAR_AUTOSTOP_AUDIT.json','V67_ABYSS_CLEAR_TRANSITION_AUDIT.json')
$text = $text.Replace('66.0.0.0','67.0.0.0')

$tmp = Join-Path $env:TEMP ('mabiauto-v67-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "v67 package delegate failed: $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
