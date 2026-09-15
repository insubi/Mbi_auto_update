param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'

$auditPath = Join-Path $SourceRoot 'V0_1_10_COMPASS_PRIORITY_FINAL_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.10 final compass-priority audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.10') { throw 'Unexpected public version in V0.1.10 final audit' }
if ($audit.technical_bridge_tag -ne 'v84') { throw 'Expected v84 technical bridge' }
if ($audit.base_technical_bridge_tag -ne 'v83') { throw 'Expected v83 base bridge' }

foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.10 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.10 source integrity mismatch: $($entry.Name)" }
}

$botPath = Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs'
$bot = Get-Content -LiteralPath $botPath -Raw
$required = @(
    'var compassPriority = _templates.MatchCompass(f.Gray, slot);',
    'bool compassPresent =',
    'bool hookHud = !compassPresent && LooksLikeFishingCastHud(f.Bgr);',
    'if (!compassPresent && (hook.Score >= hookThreshold || hookHud))',
    '시전 대기 · 나침반 우선',
    'Math.Min(_cfg.HookThreshold, 0.72)',
    'if (hookFrames >= 3)',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도'
)
foreach ($marker in $required) {
    if (-not $bot.Contains($marker)) { throw "V0.1.10 fishing invariant missing: $marker" }
}

if ($bot.Contains('bool hookHud = LooksLikeFishingCastHud(f.Bgr);')) {
    throw 'V0.1.10 still allows ungated stage1 HUD fallback'
}

$badPostMarker = '_templates.MatchCompass(f.Gray, slot).Score'
if ($bot.Contains($badPostMarker)) {
    throw 'V0.1.10 still contains the v83 post-cast slot compile regression'
}

$postMarker = 'if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72))'
$firstPost = $bot.IndexOf($postMarker)
if ($firstPost -lt 0) { throw 'V0.1.10 first conservative post-cast hook check missing' }
$secondPost = $bot.IndexOf($postMarker, $firstPost + $postMarker.Length)
if ($secondPost -lt 0) { throw 'V0.1.10 second conservative post-cast hook check missing' }

$configPath = Join-Path $SourceRoot 'FishingAutomation/config.json'
$config = Get-Content -LiteralPath $configPath -Raw
if (-not $config.Contains('"HookThreshold": 0.72')) { throw 'V0.1.10 must preserve config HookThreshold 0.72' }

$updatePath = Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs'
$update = Get-Content -LiteralPath $updatePath -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.10";')) { throw 'V0.1.10 updater version missing' }

Write-Host 'V0.1.10 FINAL SOURCE VERIFIED: compass first, S transition retained, Hook then Space, and v83 post-cast compile regression removed.'
