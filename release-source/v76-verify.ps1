param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_3_FISHING_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.3 audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.3' -or $audit.technical_bridge_tag -ne 'v76' -or $audit.base_public_version -ne 'V0.1.2') { throw 'Expected audited V0.1.3 source based on V0.1.2 with v76 bridge tag' }
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.3 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.3 source integrity mismatch: $($entry.Name)" }
}
$hook = Join-Path $SourceRoot 'FishingAutomation/templates/hook.png'
$hookHash = (Get-FileHash -LiteralPath $hook -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hookHash -ne [string]$audit.hook_template_sha256) { throw 'V0.1.3 hook hash mismatch' }
Add-Type -AssemblyName System.Drawing
$img = $null
try {
    $img = [System.Drawing.Image]::FromFile($hook)
    if ($img.Width -ne 54 -or $img.Height -ne 54) { throw "Unexpected V0.1.3 hook dimensions: $($img.Width)x$($img.Height)" }
} finally { if ($null -ne $img) { $img.Dispose() } }
$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
foreach ($marker in @('double hookThreshold = Math.Min(_cfg.HookThreshold, 0.82);','bool sent = _input.TapSpace();','Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.3 fishing invariant missing: $marker" }
}
$start = Get-Content -LiteralPath (Join-Path $SourceRoot 'START.cmd') -Raw
foreach ($name in @('hook.png','gauge.png','healthbar.png','compass.png')) {
    $marker = 'if not exist "%ROOT%\release\templates\' + $name + '" copy /y'
    if (-not $start.Contains($marker)) { throw "V0.1.3 guarded template copy missing: $name" }
}
$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.3";')) { throw 'V0.1.3 updater version missing' }
Write-Host 'V0.1.3 SOURCE VERIFIED: current fishing HUD template, guarded runtime templates, two-frame 0.82 recognition and truthful Space retry.'
