param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_10_COMPASS_PRIORITY_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.10 compass-priority audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.10' -or $audit.technical_bridge_tag -ne 'v83' -or $audit.base_public_version -ne 'V0.1.9') {
    throw 'Expected audited V0.1.10 source based on V0.1.9 with v83 bridge tag'
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
    'private static bool LooksLikeFishingCastHud(OpenCvSharp.Mat bgr)',
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.10 fishing invariant missing: $marker" }
}
if ($bot.Contains('bool hookHud = LooksLikeFishingCastHud(f.Bgr);')) { throw 'V0.1.10 still allows ungated HUD hook fallback before compass priority' }
$compassCalls = ([regex]::Matches($bot, [regex]::Escape('_templates.MatchCompass(f.Gray, slot)'))).Count
if ($compassCalls -lt 4) { throw "V0.1.10 expected compass checks in priority/original/post-cast paths, found $compassCalls" }
$hudUseCount = ([regex]::Matches($bot, [regex]::Escape('LooksLikeFishingCastHud(f.Bgr)'))).Count
if ($hudUseCount -lt 3) { throw "V0.1.10 expected retained HUD fallback in start/end/next-ready paths, found $hudUseCount" }

$config = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/config.json') -Raw
if (-not $config.Contains('"HookThreshold": 0.72')) { throw 'V0.1.10 must preserve config HookThreshold 0.72' }

$capture = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/CaptureService.cs') -Raw
foreach ($marker in @(
    'NativeMethods.GetClientRect(window.Handle, out var liveClient)',
    'NativeMethods.ClientToScreen(window.Handle, ref liveOrigin)',
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);')) {
    if (-not $capture.Contains($marker)) { throw "V0.1.7 capture invariant lost: $marker" }
}

$guard = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingFocusGuard.cs') -Raw
foreach ($marker in @('AttachThreadInput','BringWindowToTop','SetForegroundWindow','SetActiveWindow','SetFocus')) {
    if (-not $guard.Contains($marker)) { throw "V0.1.6 focus guard invariant lost: $marker" }
}

$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.10";')) { throw 'V0.1.10 updater version missing' }
Write-Host 'V0.1.10 SOURCE VERIFIED: compass recognition has strict priority, compass blocks hook/HUD Space decisions, and retained fishing recovery paths are present.'
