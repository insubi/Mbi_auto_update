param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_10_COMPASS_PRIORITY_FINAL_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.10 final compass-priority audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.10' -or $audit.technical_bridge_tag -ne 'v84' -or $audit.base_technical_bridge_tag -ne 'v83') {
    throw 'Expected audited V0.1.10 final source on v84 correcting the v83 bridge'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.10 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.10 source integrity mismatch: $($entry.Name)" }
}

$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
foreach ($marker in @(
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
    'Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.10 fishing invariant missing: $marker" }
}
if ($bot.Contains('bool hookHud = LooksLikeFishingCastHud(f.Bgr);')) { throw 'V0.1.10 still allows ungated stage1 HUD fallback' }
if ($bot.Contains('_templates.MatchCompass(f.Gray, slot).Score') -and $bot.Contains('LooksLikeFishingCastHud(f.Bgr))) {
    # Stage1 uses compassPriority; direct slot-based compass calls inside post-cast expressions caused the v83 compile failure.
    $badPost = [regex]::IsMatch($bot, 'if\s*\([^\r\n]*_templates\.MatchCompass\(f\.Gray,\s*slot\)[^\r\n]*LooksLikeFishingCastHud')
    if ($badPost) { throw 'V0.1.10 still has the v83 post-cast slot compile regression' }
}
$plainPost = ([regex]::Matches($bot, [regex]::Escape('if (hook.Score >= Math.Min(_cfg.HookThreshold, 0.72))'))).Count
if ($plainPost -lt 2) { throw "V0.1.10 expected two conservative post-cast template-only hook checks, found $plainPost" }

$config = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/config.json') -Raw
if (-not $config.Contains('"HookThreshold": 0.72')) { throw 'V0.1.10 must preserve config HookThreshold 0.72' }
$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.10";')) { throw 'V0.1.10 updater version missing' }
Write-Host 'V0.1.10 FINAL SOURCE VERIFIED: compass-first S transition is retained, post-cast slot regression removed, and conservative post-cast hook checks compile safely.'
