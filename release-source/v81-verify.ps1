param([Parameter(Mandatory=$true)][string]$SourceRoot)
$ErrorActionPreference = 'Stop'
$auditPath = Join-Path $SourceRoot 'V0_1_8_REAL_DEBUG_HOOK_AUDIT.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw 'V0.1.8 real debug hook audit missing' }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.version -ne 'V0.1.8' -or $audit.technical_bridge_tag -ne 'v81' -or $audit.base_public_version -ne 'V0.1.7') {
    throw 'Expected audited V0.1.8 source based on V0.1.7 with v81 bridge tag'
}
foreach ($entry in $audit.files.PSObject.Properties) {
    $path = Join-Path $SourceRoot $entry.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "V0.1.8 source file missing: $($entry.Name)" }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) { throw "V0.1.8 source integrity mismatch: $($entry.Name)" }
}

$bot = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingBot.cs') -Raw
$thresholdCount = ([regex]::Matches($bot, [regex]::Escape('Math.Min(_cfg.HookThreshold, 0.72)'))).Count
if ($thresholdCount -lt 3) { throw "V0.1.8 expected at least three 0.72 hook checks, found $thresholdCount" }
if ($bot.Contains('Math.Min(_cfg.HookThreshold, 0.78)')) { throw 'V0.1.8 left old 0.78 hook checks behind' }
if (-not $bot.Contains('if (hookFrames >= 3)')) { throw 'V0.1.8 three-frame hook confirmation missing' }
foreach ($marker in @(
    'GaugeAnchor? liveGauge = _templates.DetectGauge(f, _cfg, out MatchResult liveGaugeMatch);',
    'stage1_hook_wait_8s',
    'bool sent = _input.TapSpace();',
    'Space 전송 실패 -> 재시도')) {
    if (-not $bot.Contains($marker)) { throw "V0.1.8 retained fishing invariant missing: $marker" }
}

$matcher = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/TemplateMatcher.cs') -Raw
foreach ($marker in @(
    'if (primary.Score >= 0.72) return primary;',
    'gray.Width * 0.28',
    'gray.Width * 0.72',
    'gray.Height * 0.72',
    'gray.Height * 0.97',
    'MatchResult recovery = MatchVariants(gray, recoveryRoi, _hookVariants);')) {
    if (-not $matcher.Contains($marker)) { throw "V0.1.8 narrowed hook recovery invariant missing: $marker" }
}

$config = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/config.json') -Raw
if (-not $config.Contains('"HookThreshold": 0.72')) { throw 'V0.1.8 config HookThreshold is not 0.72' }

$capture = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/CaptureService.cs') -Raw
foreach ($marker in @(
    'NativeMethods.GetClientRect(window.Handle, out var liveClient)',
    'NativeMethods.ClientToScreen(window.Handle, ref liveOrigin)',
    'FishingFocusGuard.IsForeground(window.Handle)',
    'FishingFocusGuard.Activate(window.Handle);')) {
    if (-not $capture.Contains($marker)) { throw "V0.1.7 capture invariant lost: $marker" }
}

$start = Get-Content -LiteralPath (Join-Path $SourceRoot 'START.cmd') -Raw
$forcedHookCopy = 'copy /y "%ROOT%\FishingAutomation\templates\hook.png" "%ROOT%\release\templates\hook.png"'
if (-not $start.Contains($forcedHookCopy)) { throw 'V0.1.7 forced runtime hook refresh lost' }

$guard = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/FishingFocusGuard.cs') -Raw
foreach ($marker in @('AttachThreadInput','BringWindowToTop','SetForegroundWindow','SetActiveWindow','SetFocus')) {
    if (-not $guard.Contains($marker)) { throw "V0.1.6 focus guard invariant lost: $marker" }
}

$update = Get-Content -LiteralPath (Join-Path $SourceRoot 'FishingAutomation/UpdateManager.cs') -Raw
if (-not $update.Contains('public const string CurrentVersion = "V0.1.8";')) { throw 'V0.1.8 updater version missing' }
Write-Host 'V0.1.8 SOURCE VERIFIED: real-debug 0.72 hook acceptance, three-frame confirmation, narrowed lower-center recovery ROI, live capture origin and diagnostics are present.'
