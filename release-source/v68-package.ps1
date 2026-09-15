param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'

$baseScript = Join-Path $PSScriptRoot 'v66-package.ps1'
if (-not (Test-Path -LiteralPath $baseScript)) { throw 'v66 package script missing' }
$text = Get-Content -LiteralPath $baseScript -Raw
$text = $text.Replace('v66','v68')
$text = $text.Replace('V66_ABYSS_CLEAR_AUTOSTOP_AUDIT.json','V68_ABYSS_INTERNAL_RECOVERY_AUDIT.json')
$text = $text.Replace('66.0.0.0','68.0.0.0')

$tmp = Join-Path $env:TEMP ('mabiauto-v68-package-' + [Guid]::NewGuid().ToString('N') + '.ps1')
try {
    Set-Content -LiteralPath $tmp -Value $text -Encoding UTF8
    & $tmp -SourceRoot $SourceRoot -OutputRoot $OutputRoot
    if ($LASTEXITCODE -ne 0) { throw "v68 package delegate failed: $LASTEXITCODE" }
} finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
